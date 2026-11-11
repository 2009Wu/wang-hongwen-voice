"""Checksum-verified portable updates with a recoverable code backup."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,subprocess,time,urllib.request,uuid,zipfile
from pathlib import Path,PurePosixPath
from studio_paths import ROOT,PRODUCT,atomic_json,read_json,owned_path,sha256,file_lock

ALLOWED={'2009Wu/custom-voice-studio','2009Wu/wang-hongwen-voice'}
LIMIT=30*1024**2
AUTO_CHECK_INTERVAL = 6 * 60 * 60

def automatic_update_settings(root=None):
    path = (root or ROOT) / '.runtime/updates/automatic.json'
    settings = read_json(path)
    return settings if isinstance(settings, dict) else {}

def automatic_updates_enabled():
    return automatic_update_settings().get('enabled', True) is not False

def set_automatic_updates(enabled):
    settings = automatic_update_settings()
    settings['enabled'] = bool(enabled)
    if enabled:
        settings.pop('last_check', None)
    atomic_json(ROOT / '.runtime/updates/automatic.json', settings)

def prepare_automatic_update():
    # The desktop launcher calls this before starting the browser server.
    request_path = ROOT / '.runtime/update-request.json'
    if request_path.exists():
        return
    settings = automatic_update_settings()
    if settings.get('enabled', True) is False:
        return
    now = time.time()
    last_check = settings.get('last_check')
    if isinstance(last_check, (int, float)) and 0 <= now - last_check < AUTO_CHECK_INTERVAL:
        return

    # Record the attempt before networking, so a failed update cannot restart in a loop.
    settings['last_check'] = now
    atomic_json(ROOT / '.runtime/updates/automatic.json', settings)
    try:
        latest = check_update(timeout=5)
        if not latest['available']:
            return
        skipped = settings.get('skip_through')
        if skipped and version(latest['tag']) <= version(skipped):
            return
        stage = stage_update(latest=latest, timeout=5)
        atomic_json(request_path, {'kind': 'apply', 'stage': stage})
    except Exception as error:
        # Retry a transient download on the next launch, with a short cooldown.
        settings['last_check'] = now - AUTO_CHECK_INTERVAL + 30 * 60
        atomic_json(ROOT / '.runtime/updates/automatic.json', settings)
        print('自动更新检查未完成：' + str(error)[:250], flush=True)


def version(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',str(value))
    if not match:raise ValueError('更新版本号无效。')
    return tuple(map(int,match.groups()))

def download(url,limit=LIMIT,timeout=30):
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in {'api.github.com','github.com','raw.githubusercontent.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:
        raise ValueError('更新下载地址不受支持。')
    request=urllib.request.Request(url,headers={'User-Agent':'VoiceStudios-Updater','Accept':'application/vnd.github+json' if parsed.hostname=='api.github.com' else '*/*'})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        final=urlparse(response.geturl())
        if final.scheme!='https' or final.hostname not in {'api.github.com','github.com','raw.githubusercontent.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:raise ValueError('更新下载重定向地址不受支持。')
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('更新文件超出了预期大小。')
    return data

def check_update(timeout=30):
    repo=PRODUCT['repository']
    if repo not in ALLOWED:raise ValueError('项目更新来源无效。')
    release=json.loads(download(f'https://api.github.com/repos/{repo}/releases/latest',2*1024**2,timeout=timeout))
    tag=release['tag_name'];available=version(tag)>version(PRODUCT['version'])
    assets={a['name']:a['browser_download_url'] for a in release.get('assets',[])}
    if available and any(name not in assets for name in [PRODUCT['asset'],PRODUCT['asset']+'.sha256']):
        raise ValueError('新版安装包或校验文件尚未发布完整，请稍后重试。')
    if available:
        release_prefix = f'https://github.com/{repo}/releases/download/{tag}/'
        for name in (PRODUCT['asset'], PRODUCT['asset'] + '.sha256'):
            if assets[name] != release_prefix + name:
                raise ValueError('更新附件不属于当前项目的发布版本。')
    result={'tag':tag,'available':available,'assets':assets,'checked':time.time()}
    atomic_json(ROOT/'.runtime/updates/latest.json',result)
    return result

def bundle_path(root,name):
    if '\\' in name or ':' in name:raise ValueError('安装包包含不安全的文件名。')
    parts=name.split('/')
    if any(p.rstrip(' .')!=p or not p or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',p) for p in parts):raise ValueError('安装包包含无效的 Windows 文件名。')
    if not parts or name.startswith('/') or any(p.casefold() in {'.','..','.runtime','.cache','.git'} for p in parts):
        raise ValueError('安装包不能覆盖缓存、设置或外部文件。')
    return owned_path(root,Path(*parts))

def unpack_bundle(archive,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        manifest = bundle.getinfo('release-manifest.json')
        if manifest.file_size > 2 * 1024**2:
            raise ValueError('更新清单大小异常。')
        meta=json.loads(bundle.read(manifest))
        if meta['product']!=PRODUCT['id']:raise ValueError('安装包属于另一个工作室。')
        version(meta['version'])
        expected=meta['files'];names=[e.filename for e in bundle.infolist() if not e.is_dir()]
        if len(set(n.casefold() for n in names))!=len(names):raise ValueError('安装包包含重复文件名。')
        actual=set(names)
        if actual!=set(expected)|{'release-manifest.json'}:raise ValueError('安装包文件清单不一致。')
        if PRODUCT['launcher'] not in expected or 'app.py' not in expected:raise ValueError('安装包不完整。')
        total=0
        for entry in bundle.infolist():
            target=bundle_path(destination,entry.filename)
            if entry.is_dir():continue
            if (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('安装包不能包含链接。')
            total+=entry.file_size
            if entry.file_size>LIMIT or total>200*1024**2:raise ValueError('安装包解压大小异常。')
            data=bundle.read(entry)
            if entry.filename!='release-manifest.json' and hashlib.sha256(data).hexdigest()!=expected[entry.filename]:raise ValueError('安装包内部文件校验失败。')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return meta

def stage_update(latest=None, timeout=30):
    if latest is None:
        latest=check_update(timeout=timeout)
    if not latest['available']:return None
    folder=ROOT/'.runtime/updates/staged'/uuid.uuid4().hex;folder.mkdir(parents=True)
    url=latest['assets'][PRODUCT['asset']];data=download(url,timeout=timeout)
    checksum=download(latest['assets'][PRODUCT['asset']+'.sha256'],4096,timeout=timeout).decode('utf-8-sig').split()[0].lower()
    if not re.fullmatch('[0-9a-f]{64}',checksum) or hashlib.sha256(data).hexdigest()!=checksum:raise ValueError('更新包校验失败，当前版本没有改动，请重试下载。')
    archive=folder/'update.zip';archive.write_bytes(data)
    meta=unpack_bundle(archive,folder/'bundle')
    if version(meta['version'])!=version(latest['tag']):raise ValueError('更新包与发布版本不一致。')
    atomic_json(folder/'stage.json',{'version':meta['version'],'sha256':checksum})
    return str(folder)

def last_backup(root=ROOT):
    pointer=read_json(Path(root)/'.runtime/updates/last-backup.json')
    if not pointer:return None
    try:
        path=owned_path(Path(root)/'.runtime/updates/backups',pointer['id'],must_exist=True)
        return path if (path/'backup.json').is_file() else None
    except (ValueError,OSError):return None

def request_update(stage=None,rollback=False):
    from runner import GPU_LOCK
    if not GPU_LOCK.acquire(blocking=False):raise ValueError('请先停止或等待当前生成完成，再安装更新。')
    try:
        if rollback:
            backup=last_backup()
            if not backup:raise ValueError('还没有可回退的更新备份。')
            payload={'kind':'rollback','backup':str(backup)}
        else:
            if not stage:raise ValueError('请先下载并校验更新。')
            stage=owned_path(ROOT/'.runtime/updates/staged',stage,must_exist=True)
            payload={'kind':'apply','stage':str(stage)}
        if not os.getenv('VOICE_LAUNCHER_PID'):raise ValueError('请使用桌面启动器打开工作室后安装更新；直接运行源码时请手动更新。')
        atomic_json(ROOT/'.runtime/update-request.json',payload)
    finally:GPU_LOCK.release()
    return '正在关闭界面并安装更新，完成后会自动重新打开。作品、音色和模型会保留。'

def atomic_copy(source,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.update-'+uuid.uuid4().hex)
    try:shutil.copy2(source,temporary);os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)

def restore_backup(backup,root=ROOT):
    root=Path(root).resolve();backup=owned_path(root/'.runtime/updates/backups',backup,must_exist=True)
    meta=read_json(backup/'backup.json')
    if not meta or meta['product']!=PRODUCT['id']:raise ValueError('回退备份无效。')
    for name,expected in meta['files'].items():
        source=bundle_path(backup/'files',name)
        if sha256(source)!=expected:raise ValueError('回退备份校验失败。')
    # Restore the launcher last; the caller has already closed its previous process.
    names=sorted(meta['files'],key=lambda n:n==PRODUCT['launcher'])
    for name in names:atomic_copy(bundle_path(backup/'files',name),bundle_path(root,name))
    for name in meta['absent']:
        path=bundle_path(root,name)
        if path.is_file():path.unlink()
    (root/'.runtime/update-transaction.json').unlink(missing_ok=True)
    return meta

def apply_stage(stage,root=ROOT):
    root=Path(root).resolve();stage=owned_path(root/'.runtime/updates/staged',stage,must_exist=True)
    bundle=stage/'bundle';meta=read_json(bundle/'release-manifest.json')
    if not meta or meta['product']!=PRODUCT['id']:raise ValueError('更新清单无效。')
    for name,expected in meta['files'].items():
        if sha256(bundle_path(bundle,name))!=expected:raise ValueError('已暂存更新文件被改动。')
    names=set(meta['files'])|{'release-manifest.json'}
    previous=read_json(root/'release-manifest.json',{'files':{}})
    names.update(previous.get('files',{}))
    identifier=uuid.uuid4().hex;backup=root/'.runtime/updates/backups'/identifier;backup.mkdir(parents=True)
    saved={};absent=[]
    for name in names:
        path=bundle_path(root,name)
        if path.is_file():
            target=bundle_path(backup/'files',name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);saved[name]=sha256(target)
        else:absent.append(name)
    backup_meta={'id':identifier,'product':PRODUCT['id'],'files':saved,'absent':absent,'created':time.time()}
    atomic_json(backup/'backup.json',backup_meta)
    atomic_json(root/'.runtime/update-transaction.json',{'backup':str(backup)})
    try:
        for name in sorted(meta['files'],key=lambda n:n==PRODUCT['launcher']):atomic_copy(bundle_path(bundle,name),bundle_path(root,name))
        atomic_copy(bundle/'release-manifest.json',root/'release-manifest.json')
        for name in set(previous.get('files',{}))-set(meta['files']):
            target=bundle_path(root,name)
            if target.is_file():target.unlink()
        atomic_json(root/'.runtime/updates/last-backup.json',{'id':identifier})
        (root/'.runtime/update-transaction.json').unlink(missing_ok=True)
    except Exception:
        restore_backup(backup,root);raise
    return backup

def process_exists(pid):
    if pid<=0:return False
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if handle:
            code=wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
            running=bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
            kernel.CloseHandle(handle);return running
        return False
    try:os.kill(pid,0);return True
    except OSError:return False

def run_request(root,wait_pid,recover=False):
    root=Path(root).resolve();deadline=time.monotonic()+60
    while process_exists(wait_pid):
        if time.monotonic()>deadline:raise TimeoutError('启动器未能退出，更新尚未安装。')
        time.sleep(.2)
    with file_lock(root / '.runtime/updates/apply.lock'):
        handled = finish_request(root, recover)
    launcher = root / PRODUCT['launcher']
    if handled and launcher.is_file():
        subprocess.Popen([str(launcher), '--open'], cwd=root)

def finish_request(root, recover):
    request_path = root / '.runtime/update-request.json'
    transaction_path = root / '.runtime/update-transaction.json'
    if not (transaction_path if recover else request_path).exists():
        return False
    try:
        if recover:
            transaction=read_json(root/'.runtime/update-transaction.json')
            if transaction:restore_backup(transaction['backup'],root)
            message='上次更新未完成，已恢复到更新前的程序。'
        else:
            request=read_json(request_path)
            if not request:raise ValueError('没有待处理的更新请求。')
            if request['kind']=='apply':apply_stage(request['stage'],root);message='更新已安装。'
            elif request['kind']=='rollback':
                settings = automatic_update_settings(root)
                skipped = settings.get('skip_through', PRODUCT['version'])
                settings['skip_through'] = max(skipped, PRODUCT['version'], key=version)
                atomic_json(root / '.runtime/updates/automatic.json', settings)
                restore_backup(request['backup'],root)
                message='已回退到上一个版本。自动更新会等待更高版本。'
            else:raise ValueError('未知更新操作。')
        atomic_json(root/'.runtime/update-result.json',{'ok':True,'message':message})
    except Exception as error:
        atomic_json(root/'.runtime/update-result.json',{'ok':False,'message':'更新未完成：'+str(error)[:300]})
    finally:request_path.unlink(missing_ok=True)
    return not transaction_path.exists()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run-request', 'recover', 'prepare-automatic'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--wait-pid', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'prepare-automatic':
        prepare_automatic_update()
    else:
        run_request(args.root, args.wait_pid, args.command == 'recover')
