"""Preview and local replacement around the unchanged Seed-VC inference recipe."""
from pathlib import Path
from types import SimpleNamespace
import json,math,os,sys
import numpy as np
import soundfile as sf
import torch
from settings import ROOT,MAX_SECONDS,MAX_MB
from studio_paths import PRODUCT,sha256
from studio_library import workspace_for,get_record
from audio_utils import decode_input,windows,fade_weights,restore_dynamics,ffmpeg,mix_tracks,master,export_mp3,export_flac,export_video,export_video_copy

FILTER='highpass=f=70,equalizer=f=300:t=q:w=1:g=-1,equalizer=f=2800:t=q:w=1:g=1.5,acompressor=threshold=0.125:ratio=2:attack=8:release=100:makeup=1.1'

def replace_interval(base,patch,start,end,fade_samples):
    if len(patch)!=end-start or not 0<=start<end<=len(base): raise ValueError('重做片段长度或范围不正确。')
    output=base.copy();weights=np.ones(len(patch),dtype='float32');n=min(fade_samples,len(patch)//2)
    if n:
        if start:weights[:n]=np.linspace(0,1,n)
        if end<len(base):weights[-n:]=np.linspace(1,0,n)
    if base.ndim==2:weights=weights[:,None]
    output[start:end]=base[start:end]*(1-weights)+patch*weights
    return output

def generate_song(request,job,emit,separate):
    job=Path(job);steps=int(request.get('steps',40));vocal_db=float(request.get('vocal_db',4.5));music_db=float(request.get('music_db',-1.5))
    if steps not in [20,40,60] or not -2<=vocal_db<=9 or not -12<=music_db<=3:raise ValueError('生成参数无效。')
    redo=request.get('operation')=='redo';preview=bool(request.get('preview'));parent=None
    clip_start=float(request.get('clip_start',0)) if preview else 0
    clip_seconds=float(request.get('clip_seconds',15)) if preview else None
    if preview and (not math.isfinite(clip_start) or clip_start<0 or clip_seconds not in [10,15,20]):raise ValueError('试听起点或长度无效。')
    if redo:
        parent=workspace_for(request['parent_id']);record=get_record(request['parent_id'])
        source,rate=sf.read(parent/'source.wav',dtype='float32');music,music_rate=sf.read(parent/'instrumental.wav',dtype='float32',always_2d=True)
        previous,_=sf.read(parent/'model-voice.wav',dtype='float32')
        previous_processed,_=sf.read(parent/'lead-processed.wav',dtype='float32')
        a,b=float(request['redo_start']),float(request['redo_end'])
        if not (math.isfinite(a) and math.isfinite(b) and 0<=a<b<=len(source)/rate and b-a<=120):raise ValueError('重做区间超出歌曲范围，或超过 120 秒。')
        start,end=round(a*rate),round(b*rate)
        context_start,context_end=max(0,start-round(.5*rate)),min(len(source),end+round(.5*rate))
        metadata={'streams':[]};video_source=record.get('result',{}).get('video')
        request['_reference_path']=str(parent/'reference.wav')
        emit(.1,f'正在保留原作品，只重做 {a:g}–{b:g} 秒…')
    else:
        emit(.02,'正在读取歌曲试听片段…' if preview else '正在读取整首歌曲…')
        metadata,samples,rate=decode_input(Path(request['input']),job/'input.wav',MAX_SECONDS,MAX_MB,clip_start,clip_seconds)
        source,music=separate(job/'input.wav',job,request['_policy']);music_rate=rate
        if len(source)!=samples:raise RuntimeError('人声分离改变了音频长度。')
        context_start,context_end=0,len(source);video_source=None
    assert rate==music_rate and len(source)==len(music)
    sf.write(job/'source.wav',source,rate,subtype='FLOAT')
    sf.write(job/'instrumental.wav',music,rate,subtype='FLOAT')
    emit(.25,'正在载入翻唱模型（首次使用需下载）…')
    repo=ROOT/'vendor/seed_vc';sys.path.insert(0,str(repo));os.chdir(repo)
    import inference
    # Copy to the same canonical name for old and new APIs.
    import shutil
    reference=job/'reference.wav'
    if Path(request['_reference_path']).resolve()!=reference.resolve():shutil.copy2(request['_reference_path'],reference)
    args=SimpleNamespace(source='',target=str(reference),output=str(job),diffusion_steps=steps,length_adjust=1.0,
        inference_cfg_rate=.7,f0_condition=True,auto_f0_adjust=False,semi_tone_shift=0,
        checkpoint=os.getenv('SEED_CHECKPOINT'),config=os.getenv('SEED_CONFIG'),fp16=True,
        low_vram=request['_policy']['profile']!='fast')
    models=inference.load_models(args);inference.load_models=lambda _:models
    selected=source[context_start:context_end];combined=np.zeros(len(selected),dtype='float32');weights=np.zeros(len(selected),dtype='float32')
    chunks=list(windows(len(selected),40*rate,round(rate*.5)))
    for i,(a,b) in enumerate(chunks):
        emit(.3+.51*i/len(chunks),f'正在翻唱 {i+1}/{len(chunks)} · {(context_start+a)/rate:.0f}–{(context_start+b)/rate:.0f} 秒')
        chunk=selected[a:b]
        if np.sqrt(np.mean(chunk.astype('float64')**2))<.001:voice=np.zeros(len(chunk),dtype='float32')
        else:
            args.source=str(job/f'chunk-{i:03}.wav');sf.write(args.source,chunk,rate,subtype='FLOAT')
            torch.manual_seed(int(request.get('seed',42)));inference.main(args)
            out=job/f'vc_chunk-{i:03}_reference_1.0_{steps}_0.7.wav'
            voice,out_rate=sf.read(out,dtype='float32')
            if out_rate!=rate or voice.ndim!=1 or not np.isfinite(voice).all():raise RuntimeError('翻唱模型返回了无效音频。')
            voice=np.pad(voice[:len(chunk)],(0,max(0,len(chunk)-len(voice))))
        fade=fade_weights(len(chunk),round(rate*.5),i==0,i==len(chunks)-1)
        combined[a:b]+=voice*fade;weights[a:b]+=fade
    model_voice=combined/np.maximum(weights,1e-6)
    if redo:model_voice=replace_interval(previous,model_voice[start-context_start:end-context_start],start,end,round(.08*rate))
    approved=None
    if request.get('approved_preview_id'):
        approved=workspace_for(request['approved_preview_id']);old_request=json.loads((approved/'request.json').read_text(encoding='utf-8'))
        if (not old_request.get('preview') or old_request.get('input_sha256')!=request.get('input_sha256') or
            int(old_request.get('steps',40))!=steps or sha256(approved/'reference.wav')!=sha256(reference)):
            raise ValueError('试听与当前原曲、音色或质量设置不一致，请重新试听。')
        approved_voice,approved_rate=sf.read(approved/'model-voice.wav',dtype='float32')
        if approved_rate!=rate:raise ValueError('试听采样率不一致。')
        start=round(float(old_request.get('clip_start',0))*rate);end=min(len(source),start+len(approved_voice))
        model_voice=replace_interval(model_voice,approved_voice[:end-start],start,end,round(.08*rate))
    sf.write(job/'model-voice.wav',model_voice,rate,subtype='FLOAT')
    voice=restore_dynamics(model_voice,source,rate);sf.write(job/'lead-raw.wav',voice,rate,subtype='FLOAT')
    emit(.84,'正在平衡人声和伴奏…')
    ffmpeg(['-v','error','-i',job/'lead-raw.wav','-af',FILTER,'-c:a','pcm_f32le',job/'lead-processed.wav'])
    processed,_=sf.read(job/'lead-processed.wav',dtype='float32')
    if redo:processed=replace_interval(previous_processed,processed[start:end],start,end,round(.08*rate))
    if approved:
        approved_processed,_=sf.read(approved/'lead-processed.wav',dtype='float32')
        processed=replace_interval(processed,approved_processed[:end-start],start,end,round(.08*rate))
    sf.write(job/'lead-processed.wav',processed,rate,subtype='FLOAT')
    sf.write(job/'mix.wav',mix_tracks(processed,source,music,rate,vocal_db,music_db),rate,subtype='FLOAT')
    public=job/'results';public.mkdir(exist_ok=True)
    prefix='Wang-Hongwen' if PRODUCT['id']=='wang-hongwen-voice' else 'Custom-Voice'
    wav=public/(prefix+'-AI-cover.wav');mp3=wav.with_suffix('.mp3');flac=wav.with_suffix('.flac')
    emit(.88,'正在导出音频并保存作品…');master(job/'mix.wav',wav)
    # Freeze the final audible waveform outside a redo, and the accepted preview interior.
    if redo or approved:
        fresh,final_rate=sf.read(wav,dtype='float64',always_2d=True)
        previous_result=get_record(request['parent_id'] if redo else request['approved_preview_id'])['result']
        accepted,accepted_rate=sf.read(previous_result['wav'],dtype='float64',always_2d=True)
        if final_rate!=rate or accepted_rate!=rate:raise ValueError('已保存作品的采样率不一致。')
        if redo:
            if len(accepted)!=len(fresh):raise ValueError('原作品长度与重做结果不一致。')
            fresh=replace_interval(accepted,fresh[start:end],start,end,round(.08*rate))
        else:fresh=replace_interval(fresh,accepted[:end-start],start,end,round(.08*rate))
        sf.write(wav,fresh,rate,subtype='PCM_24')
    export_mp3(wav,mp3);export_flac(wav,flac)
    video=None
    if request.get('video',True):
        if redo and video_source and Path(video_source).is_file():
            video=public/(prefix+'-AI-cover.mp4');export_video_copy(video_source,wav,video)
        elif not redo and any(s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic') for s in metadata['streams']):
            video=public/(prefix+'-AI-cover.mp4');export_video(Path(request['input']),wav,video,start_seconds=clip_start)
    details={'ai_generated':True,'engine':'Seed-VC reference-only','speaker_finetuning':False,'pitch_shift_semitones':0,
        'steps':steps,'vocal_gain_db':vocal_db,'instrumental_gain_db':music_db,'instrumental_duck_db':1,
        'duration_seconds':len(source)/rate,'sample_rate':rate,'master_lufs_target':-14,'preview':preview,
        'clip_start_seconds':clip_start,'full_source_duration_seconds':float(metadata.get('format',{}).get('duration',len(source)/rate)),
        'parent_id':request.get('parent_id'),'redo_interval_seconds':[request['redo_start'],request['redo_end']] if redo else None,
        'approved_preview_reused':bool(approved),'seed':int(request.get('seed',42))}
    (public/'generation.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'audio':str(mp3),'wav':str(wav),'flac':str(flac),'video':str(video) if video else None,'details':str(public/'generation.json')}
