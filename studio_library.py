"""Persistent exports, bounded editable workspaces, and local voice favorites."""
from __future__ import annotations
import datetime as dt, os, re, shutil, time, uuid, wave
from pathlib import Path
from studio_paths import STATE, EXPORTS, HISTORY, WORKSPACES, VOICES, atomic_json, read_json, owned_path, copy_owned, sha256

def valid_id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value): raise ValueError('作品编号无效。')
    return value

def get_record(value):
    record=read_json(HISTORY/(valid_id(value)+'.json'))
    if not record: raise ValueError('找不到这条作品记录，请刷新作品列表。')
    return record

def history_choices():
    HISTORY.mkdir(parents=True,exist_ok=True)
    records=[read_json(p) for p in HISTORY.glob('*.json')]
    records=sorted((r for r in records if r),key=lambda r:r['created'],reverse=True)
    return [(r['label']+(' · 失败' if r['status']=='failed' else ''),r['id']) for r in records[:300]]

def stash_request(request, job):
    request=dict(request); private=Path(job)/'private'; private.mkdir(exist_ok=True)
    for key in ('input','reference_input'):
        if request.get(key):
            source=Path(request[key]).resolve(strict=True)
            destination=private/(key+source.suffix.lower())
            if source != destination: copy_owned(source,destination)
            request[key]=str(destination)
            if key=='input': request['input_sha256']=sha256(destination)
    return request

def archive(request, result, job, failure=None):
    job=Path(job); identifier=job.name; valid_id(identifier)
    label=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' · '+('配音' if request.get('mode')=='speak' else '翻唱')
    if request.get('preview'): label+='试听'
    if request.get('operation')=='redo': label+='局部重做'
    record={'id':identifier,'created':time.time(),'label':label,'mode':request.get('mode'),
            'preview':bool(request.get('preview')),'status':'failed' if failure else 'completed','parent':request.get('parent_id')}
    workspace=WORKSPACES/identifier; workspace.mkdir(parents=True,exist_ok=True)
    keep={'source.wav','instrumental.wav','model-voice.wav','lead-processed.wav','reference.wav','request.json'}
    for path in job.iterdir():
        if path.name in keep and path.is_file(): copy_owned(path,workspace/path.name,link=True)
    private=job/'private'
    saved_request=dict(request)
    if private.exists():
        for path in private.iterdir():
            if path.is_file():
                copied=copy_owned(path,workspace/path.name,link=True)
                for key in ('input','reference_input'):
                    if saved_request.get(key)==str(path): saved_request[key]=str(copied)
    # Request is private and may contain text. Never include it in diagnostics or releases.
    atomic_json(workspace/'request.json', {k:v for k,v in saved_request.items() if not k.startswith('_')})
    if failure:
        record['error']=str(failure)[:1000]
    else:
        destination=EXPORTS/(dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+identifier[:8])
        destination.mkdir(parents=True,exist_ok=True)
        saved=dict(result)
        for key in ('audio','wav','flac','video','details','reference'):
            if result.get(key):
                origin=Path(result[key]);target=destination/origin.name
                copy_owned(origin,target,link=True);saved[key]=str(target)
        saved['history_id']=identifier;record['result']=saved;record['directory']=str(destination)
        result=saved
    atomic_json(workspace/'state.json',{'created':record['created'],'mode':record['mode'],'preview':record['preview']})
    atomic_json(HISTORY/(identifier+'.json'),record)
    prune_workspaces(exclude=identifier)
    return result if not failure else record

def workspace_for(identifier):
    identifier=valid_id(identifier);folder=owned_path(WORKSPACES,identifier,must_exist=True)
    if not (folder/'request.json').is_file(): raise ValueError('可修改素材已清理，作品文件仍在。请重新上传原曲。')
    return folder

def retry_request(identifier, full=False):
    record=get_record(identifier);folder=workspace_for(identifier)
    request=read_json(folder/'request.json');request['parent_id']=identifier
    if full:
        if not record.get('preview'): raise ValueError('请先选择一条翻唱试听记录。')
        request['preview']=False;request['approved_preview_id']=identifier
        if 'reference_input' in request:
            request.update(reference_input=str(folder/'reference.wav'),reference_prepared=True,reference_start=0)
    return request

def redo_request(identifier,start,end):
    record=get_record(identifier);folder=workspace_for(identifier)
    if record['status']!='completed' or record['mode']!='sing' or record.get('preview'): raise ValueError('请选择一首已完成的完整翻唱。')
    for name in ('source.wav','instrumental.wav','model-voice.wav','lead-processed.wav','reference.wav'):
        if not (folder/name).is_file(): raise ValueError('这首歌的可修改素材已清理，请重新生成。')
    start,end=float(start),float(end)
    if not (0<=start<end and end-start<=120): raise ValueError('重做区间必须大于 0 秒且不超过 120 秒。')
    request=read_json(folder/'request.json');request.update(operation='redo',parent_id=identifier,
        redo_start=start,redo_end=end,preview=False,seed=int(time.time_ns()%2147483647))
    request.pop('approved_preview_id',None)
    return request

def prune_workspaces(exclude=None):
    WORKSPACES.mkdir(parents=True,exist_ok=True)
    limit=int(os.getenv('VOICE_WORKSPACE_LIMIT_MB','5120'))*1024**2
    age=int(os.getenv('VOICE_WORKSPACE_DAYS','7'))*86400
    entries=[]
    for directory in WORKSPACES.iterdir():
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction(): continue
        state=read_json(directory/'state.json')
        if not state: continue
        size=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and not p.is_symlink())
        entries.append((state['created'],directory,size))
    total=sum(item[2] for item in entries)
    for created,directory,size in sorted(entries):
        if directory.name==exclude: continue
        if time.time()-created>age or total>limit:
            shutil.rmtree(owned_path(WORKSPACES,directory,must_exist=True));total-=size

def voice_choices():
    VOICES.mkdir(parents=True,exist_ok=True)
    rows=[(read_json(p),p.parent.name) for p in VOICES.glob('*/voice.json')]
    return [(r['name'],identifier) for r,identifier in rows if r]

def save_voice(name, reference, text='', language='Auto'):
    name=str(name or '').strip()
    if not 1<=len(name)<=60: raise ValueError('请给音色起一个 1–60 字的名字。')
    source=Path(reference).resolve(strict=True)
    with wave.open(str(source),'rb') as audio:
        seconds=audio.getnframes()/audio.getframerate()
    if not 3<=seconds<=25.1: raise ValueError('请先预览并选择 3–25 秒参考片段。')
    identifier=uuid.uuid4().hex;folder=VOICES/identifier;folder.mkdir(parents=True)
    copy_owned(source,folder/'reference.wav')
    atomic_json(folder/'voice.json',{'id':identifier,'name':name,'text':text or '', 'language':language,'seconds':seconds})
    return identifier

def load_voice(identifier):
    folder=owned_path(VOICES,valid_id(identifier),must_exist=True)
    item=read_json(folder/'voice.json')
    if not item: raise ValueError('音色记录不可用。')
    return str(owned_path(folder,'reference.wav',must_exist=True)),item

def delete_voice(identifier):
    folder=owned_path(VOICES,valid_id(identifier),must_exist=True)
    shutil.rmtree(folder)

def open_exports(identifier=None):
    folder=EXPORTS if not identifier else Path(get_record(identifier).get('directory',str(EXPORTS)))
    folder.mkdir(parents=True,exist_ok=True)
    if folder!=EXPORTS: owned_path(EXPORTS,folder,must_exist=True)
    if os.name=='nt': os.startfile(str(folder))
    return str(folder)
