"""Shared desktop workflow; model imports remain in isolated worker processes."""
import json,os,subprocess,uuid,time,shutil
from pathlib import Path
import gradio as gr
from settings import ROOT,SING_PYTHON,LANGUAGES,MAX_TEXT,MAX_MB
from studio_paths import PRODUCT,STATE,EXPORTS,SHARED_CACHE,read_json
from studio_library import (history_choices,get_record,retry_request,redo_request,
    voice_choices,save_voice,load_voice,delete_voice,open_exports)
from runner import run_job

MEDIA=['.mp3','.mp4','.wav','.m4a','.flac','.ogg','.webm','.mov','.aac','.mkv']

def prepare_clip(source,start=0,seconds=20,exact=False):
    if not source:raise ValueError('请先上传参考人声。')
    preview_root=STATE/'reference-previews';preview_root.mkdir(parents=True,exist_ok=True)
    from studio_paths import owned_path
    for old in preview_root.iterdir():
        if old.is_dir() and not old.is_symlink() and not old.is_junction() and time.time()-old.stat().st_mtime>7*86400:
            shutil.rmtree(owned_path(preview_root,old,must_exist=True))
    folder=preview_root/uuid.uuid4().hex
    command=[SING_PYTHON,str(ROOT/'studio_actions.py'),str(source),str(folder),
        '--start',str(start),'--seconds',str(seconds)]
    if exact:command+=['--prepared']
    env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    done=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,**options)
    if done.returncode:
        for line in reversed(done.stderr.splitlines()):
            if line.startswith(('ValueError:','RuntimeError:')):raise ValueError(line.split(':',1)[1].strip())
        raise ValueError('无法读取参考声音，请检查素材或在启动器修复安装。')
    return json.loads(done.stdout.strip().splitlines()[-1])

def result_values(result,message):
    return (result.get('audio'),result.get('audio'),result.get('flac'),result.get('wav'),
        result.get('video'),result.get('details'),result.get('reference'),result.get('reference_text',''),
        message,gr.update(choices=history_choices(),value=result.get('history_id')),result.get('history_id'))

def build_app(api):
    custom=PRODUCT['id']=='custom-voice-studio'
    def work(request,progress):
        try:
            for fraction,message,result in run_job(request):
                progress(fraction,desc=message)
                if result:yield result_values(result,message+'\n保存位置：'+str(Path(result['audio']).parent))
                else:yield *(gr.skip() for _ in range(8)),message,gr.skip(),gr.skip()
        except Exception as error:raise gr.Error(str(error)) from error

    with gr.Blocks(title=PRODUCT['name'],delete_cache=(600,3600)) as demo:
        gr.Markdown('# '+PRODUCT['name']+'\n'+('上传参考人声，再输入文字或放入歌曲。' if custom else '输入文字，或放入有原唱的音频／视频。')+'生成后会自动保存作品。')
        with gr.Tab('生成作品'):
            with gr.Row(equal_height=False):
                with gr.Column(scale=6):
                    if custom:
                        favorite=gr.Dropdown(choices=voice_choices(),label='收藏的音色',value=None)
                        reference=gr.File(label='参考人声 · MP3 / MP4 等',file_types=MEDIA,type='filepath')
                        with gr.Accordion('先听参考片段 / 收藏音色',open=False):
                            ref_start=gr.Number(value=0,minimum=0,maximum=3600,label='从第几秒开始寻找清晰讲话')
                            ref_seconds=gr.Dropdown([5,10,15,20,25],value=20,label='参考片段最长秒数')
                            inspect=gr.Button('提取并试听参考片段')
                            selected_ref=gr.Audio(label='参考片段（可拖动裁剪，保留 3–25 秒）',type='filepath',editable=True)
                            ref_hint=gr.Textbox(label='参考片段信息',interactive=False)
                            ref_text=gr.Textbox(label='参考片段原话（留空自动识别）',lines=2)
                            ref_lang=gr.Dropdown(LANGUAGES,value='Auto',label='参考讲话语言')
                            voice_name=gr.Textbox(label='收藏名称',placeholder='例如：我的声音')
                            with gr.Row():
                                save=gr.Button('收藏这个音色');remove=gr.Button('移除选中的收藏')
                    else:
                        reference=gr.State(None);selected_ref=gr.State(None)
                        ref_start=gr.State(0);ref_seconds=gr.State(20);ref_text=gr.State('');ref_lang=gr.State('Auto')
                    text=gr.Textbox(label='输入文字 → 配音',lines=4,placeholder='输入想朗读的内容……')
                    song=gr.File(label='上传歌曲或视频 → 翻唱',file_types=MEDIA,type='filepath')
                    gr.Markdown(f'文字与歌曲任选一种。最多 {MAX_TEXT} 字；文件不超过 {MAX_MB} MB。')
                    with gr.Accordion('高级选项',open=False):
                        performance=gr.Dropdown([('自动选择','auto'),('6 GB 节省显存','low'),('8 GB 均衡','balanced'),('12 GB+ 性能优先','fast')],value='auto',label='性能档位')
                        steps=gr.Dropdown([('快速 · 20 步',20),('标准 · 40 步',40),('精细 · 60 步',60)],value=40,label='翻唱质量')
                        vocals=gr.Slider(-2,9,value=4.5,step=.5,label='人声响度（dB）')
                        music=gr.Slider(-12,3,value=-1.5,step=.5,label='伴奏响度（dB）')
                        video=gr.Checkbox(True,label='输入为视频时同时导出 MP4')
                        language=gr.Dropdown(LANGUAGES,value='Chinese',label='配音语言')
                    with gr.Row():
                        create=gr.Button('一键生成',variant='primary');stop=gr.Button('停止')
                    with gr.Accordion('先试听一小段歌曲',open=True):
                        with gr.Row():
                            clip_start=gr.Number(value=0,minimum=0,label='试听起点（秒）')
                            clip_seconds=gr.Dropdown([10,15,20],value=15,label='试听长度（秒）')
                        preview=gr.Button('生成歌曲试听')
                        approved=gr.Button('满意了，沿用这段试听生成整首')
                with gr.Column(scale=5):
                    status=gr.Textbox(label='进度 / 保存位置',value='等待文字或歌曲。',interactive=False,lines=3)
                    audio=gr.Audio(label='生成结果 · AI 合成',type='filepath',interactive=False)
                    mp3=gr.DownloadButton('下载 MP3');flac=gr.DownloadButton('下载 FLAC · 无损')
                    with gr.Accordion('更多文件',open=False):
                        wav=gr.DownloadButton('下载 WAV');movie=gr.DownloadButton('下载 MP4');details=gr.DownloadButton('生成参数')
                        used=gr.Audio(label='实际使用的参考声音',type='filepath',interactive=False)
                        transcript=gr.Textbox(label='参考原话',interactive=False)
                    folder=gr.Button('打开作品文件夹')
                    current=gr.State(None)
        with gr.Tab('作品历史'):
            history=gr.Dropdown(choices=history_choices(),label='已保存作品',value=None)
            refresh=gr.Button('刷新作品列表');load=gr.Button('载入作品到播放器')
            gr.Markdown('载入后在“生成作品”中播放或下载。作品永久保留；局部修改素材保留 7 天，总量上限约 5 GB，超出后先清理旧素材。')
            with gr.Row():
                redo_start=gr.Number(value=0,minimum=0,label='重做起点（秒）');redo_end=gr.Number(value=10,minimum=0,label='重做终点（秒）')
            redo=gr.Button('只重做这个区间（最多 120 秒）')
            retry=gr.Button('重试所选任务');history_full=gr.Button('用所选试听生成整首')
        with gr.Tab('更新与帮助'):
            gr.Markdown(f'当前版本 **{PRODUCT["version"]}**\n\n作品目录：`{EXPORTS}`\n\n两个工作室共用模型缓存：`{SHARED_CACHE}`。音色收藏和作品记录分别保存。')
            from studio_update import automatic_updates_enabled, set_automatic_updates
            automatic = gr.Checkbox(
                label='启动时自动更新', value=automatic_updates_enabled(),
                info='打开工作室时检查并安装新版，然后进入网页。离线时会继续打开当前版本。',
                visible=bool(os.getenv('VOICE_LAUNCHER_PID')),
            )
            update_info=gr.Textbox(label='更新状态',value=(read_json(ROOT/'.runtime/update-result.json') or {}).get('message','可手动检查更新。'),interactive=False)
            with gr.Row():
                check=gr.Button('检查更新');download=gr.Button('下载并校验新版')
                install=gr.Button('安装已下载更新并重启');rollback=gr.Button('回退到上一个版本')
            staged=gr.State(None)
            gr.Markdown('更新前先停止生成。安装和回退会关闭并重新打开工作室，作品、收藏音色和模型不受影响。回退后，自动更新会等待更高版本。')
            diagnose=gr.Button('导出诊断报告');report=gr.File(label='诊断报告（不含录音、输入文字和作品）',interactive=False)
            gr.Markdown('显存不足：关闭其他显卡程序，选择“6 GB 节省显存”。下载失败：检查网络后重试，保留已有缓存。无法启动：在启动器点击“修复安装”。')
        gr.Markdown('所有输出均为 AI 合成，不能作为本人真实录音。素材与生成均在本机处理。')
        outputs=[audio,mp3,flac,wav,movie,details,used,transcript,status,history,current]
        inputs=[reference,selected_ref,text,song,performance,steps,vocals,music,video,language,ref_start,ref_seconds,ref_text,ref_lang,clip_start,clip_seconds]
        def make(values,is_preview):
            reference,selected,text,song,performance,steps,vocals,music,video,language,rs,rl,rt,lang,cs,cl=values
            if custom:
                request=api['make_request'](selected or reference,text,song,performance,steps,vocals,music,video,language,0 if selected else rs,rl,rt,lang)
                if selected:request['reference_prepared']=True
            else:request=api['make_request'](text,song,performance,steps,vocals,music,video,language)
            if is_preview:
                if request['mode']!='sing':raise ValueError('歌曲试听需要上传歌曲，并清空文字输入。')
                request.update(preview=True,clip_start=float(cs),clip_seconds=float(cl))
            return request
        def generate(*values,progress=gr.Progress()):
            try:request=make(values,False)
            except Exception as error:raise gr.Error(str(error)) from error
            yield from work(request,progress)
        def audition(*values,progress=gr.Progress()):
            try:request=make(values,True)
            except Exception as error:raise gr.Error(str(error)) from error
            yield from work(request,progress)
        def repeat(identifier,progress=gr.Progress()):
            try:request=retry_request(identifier)
            except Exception as error:raise gr.Error(str(error)) from error
            yield from work(request,progress)
        def full(identifier,progress=gr.Progress()):
            try:request=retry_request(identifier,full=True)
            except Exception as error:raise gr.Error(str(error)) from error
            yield from work(request,progress)
        def replace(identifier,start,end,progress=gr.Progress()):
            try:request=redo_request(identifier,start,end)
            except Exception as error:raise gr.Error(str(error)) from error
            yield from work(request,progress)
        events=[]
        for button,fn,args,name in [(create,generate,inputs,'create'),(preview,audition,inputs,'preview'),
                (approved,full,[current],False),(history_full,full,[history],False),
                (redo,replace,[history,redo_start,redo_end],'redo'),(retry,repeat,[history],False)]:
            events.append(button.click(fn,args,outputs,api_name=name,concurrency_limit=1,concurrency_id='gpu'))
        stop.click(lambda:'已停止，已完成的作品仍然保留。',outputs=status,cancels=events,queue=False,api_name=False)
        def load_history(identifier):
            try:
                record=get_record(identifier)
                if record['status']=='failed':return *(gr.skip() for _ in range(8)),record['error'],gr.skip(),identifier
                return result_values(record['result'],'已载入：'+record['directory'])
            except Exception as error:raise gr.Error(str(error)) from error
        load.click(load_history,[history],outputs,api_name=False)
        refresh.click(lambda:gr.update(choices=history_choices()),outputs=history,api_name=False)
        folder.click(lambda identifier:'作品目录：'+open_exports(identifier),[current],status,api_name=False)
        if custom:
            def inspect_reference(source,start,seconds):
                try:
                    info=prepare_clip(source,start,seconds)
                    return info['path'],f'起点 {info["clip_start_seconds"]:g} 秒 · {info["clip_duration_seconds"]:g} 秒。请先听一遍；多人、杂音或音乐较多会影响相似度。',''
                except Exception as error:raise gr.Error(str(error)) from error
            inspect.click(inspect_reference,[reference,ref_start,ref_seconds],[selected_ref,ref_hint,ref_text],api_name=False)
            reference.change(lambda:(None,'',None),outputs=[selected_ref,ref_text,favorite],api_name=False)
            selected_ref.input(lambda:'',outputs=ref_text,api_name=False)
            def save_favorite(name,clip,text,language):
                try:
                    info=prepare_clip(clip,exact=True);identifier=save_voice(name,info['path'],text,language)
                    return gr.update(choices=voice_choices(),value=identifier),'已收藏，之后可以直接选择这个音色。'
                except Exception as error:raise gr.Error(str(error)) from error
            save.click(save_favorite,[voice_name,selected_ref,ref_text,ref_lang],[favorite,ref_hint],api_name=False)
            def choose_voice(identifier):
                if not identifier:return gr.skip(),gr.skip(),gr.skip(),gr.skip()
                try:
                    path,item=load_voice(identifier)
                    return path,item['text'],item['language'],item['name']
                except Exception as error:raise gr.Error(str(error)) from error
            favorite.change(choose_voice,[favorite],[selected_ref,ref_text,ref_lang,voice_name],api_name=False)
            def remove_voice(identifier):
                try:delete_voice(identifier);return gr.update(choices=voice_choices(),value=None),None,'已移除收藏；原始素材和已有作品仍然保留。'
                except Exception as error:raise gr.Error(str(error)) from error
            remove.click(remove_voice,[favorite],[favorite,selected_ref,ref_hint],api_name=False)
        from studio_update import check_update,stage_update,request_update
        def update_check():
            try:
                result=check_update();return ('可更新到 '+result['tag']) if result['available'] else '当前已是最新发布版本。'
            except Exception as error:return '检查失败：'+str(error)[:250]
        def update_download():
            try:
                path=stage_update();return path,'新版已下载并通过校验，点击安装后会重启。' if path else '当前已是最新发布版本。'
            except Exception as error:return None,'下载失败：'+str(error)[:250]
        def update_install(path):
            try:return request_update(path)
            except Exception as error:raise gr.Error(str(error)) from error
        def update_rollback():
            try:return request_update(rollback=True)
            except Exception as error:raise gr.Error(str(error)) from error
        def save_automatic_update(enabled):
            set_automatic_updates(enabled)
            return '已开启自动更新，下次打开工作室时生效。' if enabled else '已关闭自动更新。'
        automatic.input(save_automatic_update, inputs=automatic, outputs=update_info, api_name=False, queue=False)
        check.click(update_check,outputs=update_info,api_name=False)
        download.click(update_download,outputs=[staged,update_info],api_name=False)
        install.click(update_install,[staged],update_info,api_name=False,queue=False)
        rollback.click(update_rollback,outputs=update_info,api_name=False,queue=False)
        from studio_diagnostics import export_report
        diagnose.click(export_report,outputs=report,api_name=False)
        # Original endpoints retain their exact positional inputs and outputs.
        with gr.Column(visible=False):
            legacy=gr.Button('legacy generate');legacy_status=gr.Textbox()
            if custom:
                legacy.click(api['generate'],[reference,text,song,performance,steps,vocals,music,video,language,ref_start,ref_seconds,ref_text,ref_lang],
                    [audio,mp3,flac,wav,movie,details,used,transcript,legacy_status],api_name='generate',concurrency_id='gpu',concurrency_limit=1)
            else:
                legacy.click(api['generate'],[text,song,performance,steps,vocals,music,video,language],
                    [audio,mp3,flac,wav,movie,details,legacy_status],api_name='generate',concurrency_id='gpu',concurrency_limit=1)
                a=gr.Button('legacy sing');b=gr.Button('legacy speak')
                a.click(api['singing'],[song,vocals,music,steps,video],[audio,wav,mp3,movie,details,legacy_status],api_name='sing',concurrency_id='gpu',concurrency_limit=1)
                b.click(api['speech'],[text,language],[audio,wav,mp3,details,legacy_status],api_name='speak',concurrency_id='gpu',concurrency_limit=1)
    return demo
