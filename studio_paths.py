"""User-owned persistent data and shared immutable model cache (stdlib only)."""
from __future__ import annotations
import contextlib, hashlib, json, os, shutil, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRODUCT = json.loads((ROOT / 'studio-version.json').read_text(encoding='utf-8'))
DESKTOP = os.name == 'nt' or os.getenv('VOICE_STUDIO_DESKTOP') == '1'
DATA = Path(os.getenv('VOICE_STUDIO_DATA_HOME', str(Path(os.getenv('LOCALAPPDATA', str(Path.home()/'.local/share'))) / 'VoiceStudios'))).resolve()
STATE = DATA / PRODUCT['id']
SHARED_CACHE = DATA / 'models'

def documents():
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                return Path(os.path.expandvars(winreg.QueryValueEx(key, 'Personal')[0]))
        except OSError:
            pass
    return Path.home() / 'Documents'

EXPORTS = Path(os.getenv('VOICE_STUDIO_OUTPUT_HOME', str(documents() / 'Voice Studio作品' / PRODUCT['name']))).resolve()
HISTORY = STATE / 'history'
WORKSPACES = STATE / 'workspaces'
VOICES = STATE / 'voices'

def model_cache():
    return Path(os.getenv('MODEL_CACHE', str(SHARED_CACHE if DESKTOP else ROOT/'.cache'))).resolve()

def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)

def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def owned_path(root, value, must_exist=False):
    root = Path(root).resolve(); candidate = Path(value)
    if not candidate.is_absolute(): candidate = root / candidate
    resolved = candidate.resolve(strict=must_exist)
    if resolved == root or not resolved.is_relative_to(root): raise ValueError('文件位置不属于本工作室。')
    current = candidate
    while current != root and current.is_relative_to(root):
        if current.is_symlink() or current.is_junction(): raise ValueError('不支持链接目录中的工作室文件。')
        current = current.parent
    return resolved

def copy_owned(source, destination, link=False):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try: os.link(source, destination); return destination
        except OSError: pass
    shutil.copy2(source, destination)
    return destination

@contextlib.contextmanager
def file_lock(path, seconds=120):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0); handle.write(b'0'); handle.flush(); until = time.monotonic()+seconds
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt; msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl; fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= until: raise TimeoutError('另一个工作室正在整理模型，请稍后重试。')
                time.sleep(.1)
        try: yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt; msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl; fcntl.flock(handle, fcntl.LOCK_UN)

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b''): digest.update(block)
    return digest.hexdigest()

def migrate_cache(legacy):
    legacy = Path(legacy).resolve(); target = model_cache()
    report = {'source': str(legacy), 'shared_cache': str(target), 'linked': 0, 'copied': 0, 'deduplicated_bytes': 0, 'conflicts': 0}
    if legacy == target or not legacy.is_dir(): return report
    # Only model/cache namespaces, never credentials, installation files, or arbitrary paths.
    with file_lock(target / '.migration.lock'):
        for namespace in ('huggingface/hub', 'torch', 'numba'):
            folder = legacy/namespace
            if not folder.is_dir() or folder.is_symlink() or folder.is_junction(): continue
            for parent, directories, files in os.walk(folder, followlinks=False):
                directories[:] = [d for d in directories if d != '.locks' and not (Path(parent)/d).is_symlink() and not (Path(parent)/d).is_junction()]
                for name in files:
                    source = Path(parent)/name
                    if source.is_symlink() or name.endswith(('.lock','.incomplete','.log')): continue
                    destination = target/source.relative_to(legacy)
                    owned_path(target, destination)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists():
                        try: os.link(source, destination); report['linked'] += 1
                        except OSError: shutil.copy2(source, destination); report['copied'] += 1
                    elif os.path.samefile(source, destination): continue
                    elif source.stat().st_size == destination.stat().st_size and sha256(source) == sha256(destination):
                        # Replace only the legacy cache file, after validating identical content.
                        temporary = source.with_name(source.name+'.shared-'+uuid.uuid4().hex)
                        try:
                            os.link(destination, temporary); size=source.stat().st_size
                            os.replace(temporary, source); report['deduplicated_bytes'] += size
                        except OSError: temporary.unlink(missing_ok=True)
                    else: report['conflicts'] += 1
    return report

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != 'migrate-cache': raise SystemExit('Usage: studio_paths.py migrate-cache LEGACY_CACHE')
    report = migrate_cache(sys.argv[2]); atomic_json(STATE/'cache-migration.json', report)
    print(json.dumps(report, ensure_ascii=True))


def public_output_paths():
    # Only files intentionally exposed by UI controls, never requests or history JSON.
    return [str(EXPORTS),str(VOICES),str(STATE/'reference-previews'),str(STATE/'diagnostics')]
