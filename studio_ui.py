"""Shared desktop workflow; model imports remain in isolated worker processes."""
import json,os,subprocess,uuid,time,shutil
from pathlib import Path
import gradio as gr
from settings import ROOT,SING_PYTHON,LANGUAGES,MAX_TEXT,MAX_MB
from studio_paths import PRODUCT,STATE,EXPORTS,SHARED_CACHE,read_json
from studio_library import (history_choices,get_record,retry_request,redo_request,
    voice_choices,save_voice,load_voice,delete_voice,open_exports)
from runner import run_job
from studio_presentation import ACCENT, I18N, LOCALE_CONTROL, portrait, tr

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

def upload_field(label, identifier, height):
    with gr.Column(min_width=0, elem_classes=['studio-upload-field'], elem_id=identifier):
        gr.Markdown(tr(label), elem_id=f'{identifier}-label',
                    elem_classes=['studio-field-label'], container=False)
        return gr.File(label=tr(label), show_label=False, container=False,
                       file_types=MEDIA, type='filepath', height=height,
                       elem_classes=['studio-file'])


def build_app(api):
    custom=PRODUCT['id']=='custom-voice-studio'
    def work(request,progress):
        try:
            for fraction,message,result in run_job(request):
                progress(fraction,desc=message)
                if result:yield result_values(result,message+'\n保存位置：'+str(Path(result['audio']).parent))
                else:yield *(gr.skip() for _ in range(8)),message,gr.skip(),gr.skip()
        except Exception as error:raise gr.Error(str(error)) from error

    with gr.Blocks(title=PRODUCT['name'], fill_width=True, delete_cache=(600,3600)) as demo:
        with gr.Row(elem_id='studio-hero', elem_classes=[f'studio-{ACCENT}']):
            if ACCENT == 'wang':
                gr.HTML(portrait(), scale=0, min_width=0, elem_classes=['studio-portrait'])
            with gr.Column(scale=3, min_width=232):
                gr.Markdown(I18N('studio_hero'), elem_id='studio-hero-copy')
            with gr.Column(scale=1, min_width=0, elem_classes=['studio-header-column']):
                with gr.Row(elem_id='studio-header-actions', equal_height=False):
                    gr.HTML(LOCALE_CONTROL, elem_id='studio-language', scale=0, min_width=110)
                    gr.Button(tr('给小王买杯咖啡'), link='https://ko-fi.com/little_wang',
                              link_target='_blank', scale=0, min_width=146, elem_id='support-project')
        with gr.Tabs(elem_id='studio-main-tabs'):
            with gr.Tab(tr('生成作品'), id='studio-create'):
                with gr.Row(equal_height=False, elem_classes=['studio-workspace']):
                    with gr.Column(scale=4, min_width=292, elem_classes=['studio-card', 'studio-compose']):
                        gr.Markdown('## ' + str(tr('输入与设置')), header_links=False, elem_classes=['studio-card-heading'])
                        reference=gr.State(None);selected_ref=gr.State(None)
                        ref_start=gr.State(0);ref_seconds=gr.State(20);ref_text=gr.State('');ref_lang=gr.State('Auto')
                        text=gr.Textbox(label=tr('输入文字 → 配音'),lines=4,placeholder=tr('输入想朗读的内容……'))
                        song = upload_field('上传歌曲或视频 → 翻唱', 'studio-song-upload', 118)
                        gr.Markdown(I18N('studio_limits'), elem_classes=['studio-limits'])
                        with gr.Accordion(tr('高级选项'),open=False):
                            performance=gr.Dropdown([(tr('自动选择'),'auto'),(tr('6 GB 节省显存'),'low'),(tr('8 GB 均衡'),'balanced'),(tr('12 GB+ 性能优先'),'fast')],value='auto',label=tr('性能档位'))
                            steps=gr.Dropdown([(tr('快速 · 20 步'),20),(tr('标准 · 40 步'),40),(tr('精细 · 60 步'),60)],value=40,label=tr('翻唱质量'))
                            vocals=gr.Slider(-2,9,value=4.5,step=.5,label=tr('人声响度（dB）'))
                            music=gr.Slider(-12,3,value=-1.5,step=.5,label=tr('伴奏响度（dB）'))
                            video=gr.Checkbox(True,label=tr('输入为视频时同时导出 MP4'))
                            language=gr.Dropdown(LANGUAGES,value='Chinese',label=tr('配音语言'))
                        with gr.Row():
                            create=gr.Button(tr('一键生成'),variant='primary');stop=gr.Button(tr('停止'))
                    with gr.Column(scale=6, min_width=272, elem_classes=['studio-card', 'studio-output']):
                        gr.Markdown('## ' + str(tr('试听与导出')), header_links=False, elem_classes=['studio-card-heading'])
                        audio=gr.Audio(label=tr('生成结果 · AI 合成'),type='filepath',interactive=False, elem_classes=['studio-sound'])
                        status=gr.Textbox(label=tr('进度 / 保存位置'),value=tr('等待文字或歌曲。'),interactive=False,lines=2,elem_classes=['studio-status'])
                        with gr.Accordion(tr('先试听一小段歌曲'),open=True, elem_classes=['studio-preview']):
                            with gr.Row():
                                clip_start=gr.Number(value=0,minimum=0,label=tr('试听起点（秒）'))
                                clip_seconds=gr.Dropdown([10,15,20],value=15,label=tr('试听长度（秒）'))
                            with gr.Row(elem_classes=['studio-utilities']):
                                preview = gr.Button(tr('生成歌曲试听'))
                                approved = gr.Button(tr('满意了，沿用这段试听生成整首'))
                        with gr.Row(elem_classes=['studio-utilities']):
                            mp3=gr.DownloadButton(tr('下载 MP3'))
                            flac=gr.DownloadButton(tr('下载 FLAC · 无损'))
                        with gr.Accordion(tr('更多文件'),open=False):
                            wav=gr.DownloadButton(tr('下载 WAV'));movie=gr.DownloadButton(tr('下载 MP4'));details=gr.DownloadButton(tr('生成参数'))
                            used=gr.Audio(label=tr('实际使用的参考声音'),type='filepath',interactive=False)
                            transcript=gr.Textbox(label=tr('参考原话'),interactive=False)
                        folder=gr.Button(tr('打开作品文件夹'))
                        current=gr.State(None)
            with gr.Tab(tr('作品历史'), id='studio-history'):
                history=gr.Dropdown(choices=history_choices(),label=tr('已保存作品'),value=None)
                refresh=gr.Button(tr('刷新作品列表'));load=gr.Button(tr('载入作品到播放器'))
                gr.Markdown(tr('载入后在“生成作品”中播放或下载。作品永久保留；局部修改素材保留 7 天，总量上限约 5 GB，超出后先清理旧素材。'))
                with gr.Row():
                    redo_start=gr.Number(value=0,minimum=0,label=tr('重做起点（秒）'));redo_end=gr.Number(value=10,minimum=0,label=tr('重做终点（秒）'))
                redo=gr.Button(tr('只重做这个区间（最多 120 秒）'))
                retry=gr.Button(tr('重试所选任务'));history_full=gr.Button(tr('用所选试听生成整首'))
            with gr.Tab(tr('更新与帮助'), id='studio-help'):
                gr.Markdown(I18N('studio_about'))
                from studio_update import automatic_updates_enabled, set_automatic_updates
                automatic = gr.Checkbox(
                    label=tr('启动时自动更新'), value=automatic_updates_enabled(),
                    info=tr('打开工作室时检查并安装新版，然后进入网页。离线时会继续打开当前版本。'),
                    visible=bool(os.getenv('VOICE_LAUNCHER_PID')),
                )
                update_info=gr.Textbox(label=tr('更新状态'),value=(read_json(ROOT/'.runtime/update-result.json') or {}).get('message',tr('可手动检查更新。')),interactive=False)
                with gr.Row():
                    check=gr.Button(tr('检查更新'));download=gr.Button(tr('下载并校验新版'))
                    install=gr.Button(tr('安装已下载更新并重启'));rollback=gr.Button(tr('回退到上一个版本'))
                staged=gr.State(None)
                gr.Markdown(tr('更新前先停止生成。安装和回退会关闭并重新打开工作室，作品、收藏音色和模型不受影响。回退后，自动更新会等待更高版本。'))
                diagnose=gr.Button(tr('导出诊断报告'));report=gr.File(label=tr('诊断报告（不含录音、输入文字和作品）'),interactive=False)
                gr.Markdown(tr('显存不足：关闭其他显卡程序，选择“6 GB 节省显存”。下载失败：检查网络后重试，保留已有缓存。无法启动：在启动器点击“修复安装”。'))
        gr.Markdown(tr('所有输出均为 AI 合成，不能作为本人真实录音。素材与生成均在本机处理。'), elem_id='studio-footnote')
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
