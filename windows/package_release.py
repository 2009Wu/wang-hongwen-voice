"""Build a Windows source/app ZIP without runtime caches or local settings.

Run with Python 3.12+: python windows/package_release.py --output-dir dist
The prebuilt launcher is packaged unchanged. Rebuild it separately after C# edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT_FILES = {
    '.dockerignore', '.gitattributes', '.gitignore', 'CHANGELOG.md',
    'Dockerfile', 'LICENSE', 'README.en.md', 'README.md', 'START HERE.txt',
    'Start Voice Studio.exe', 'THIRD_PARTY_NOTICES.md', 'VALIDATION.md',
    'app.py', 'audio_utils.py', 'models.json', 'requirements-singing.txt',
    'requirements-tts.txt', 'requirements-ui.txt', 'runner.py', 'settings.py',
    'worker.py', 'performance.py', '开始使用.txt',
}
DIRECTORIES = ('assets', 'docs', 'tests', 'vendor', 'windows')
EXCLUDED = {'.git', '.runtime', '.cache', '__pycache__', '.pytest_cache',
            '.venv', 'venv', 'node_modules', 'jobs', 'results', 'checkpoints'}
REQUIRED = ROOT_FILES | {
    'docs/Windows-Setup.zh-CN.md', 'docs/Windows-Setup.md',
    'windows/runtime-pins.json', 'windows/VoiceStudioLauncher.cs',
    'windows/package_release.py', 'assets/singing-reference.wav',
    'assets/speech-reference.wav', 'vendor/seed_vc/LICENSE',
}


def build(root: Path, output_dir: Path) -> dict:
    root, output_dir = root.resolve(), output_dir.resolve()
    files = [root / name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        files.extend((root / directory).rglob('*'))
    selected = {}
    for path in files:
        relative = path.relative_to(root)
        if (not path.is_file() or any(part in EXCLUDED for part in relative.parts)
                or path.suffix.lower() in {'.pyc', '.pyo', '.log'}
                or any(part == '.env' or part.startswith('.env.') for part in relative.parts)):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlinks cannot be packaged: {relative}')
        data = path.read_bytes()
        if len(data) > 25 * 1024 * 1024:
            raise ValueError(f'Unexpected large source file: {relative}')
        if path.suffix.lower() in {'.py', '.md', '.txt', '.json', '.cs', '.ps1', '.yaml', '.yml'}:
            content = data.decode('utf-8-sig')
            if re.search(r'(?i)[a-z]:\\Users\\[^\\\r\n]+\\', content):
                raise ValueError(f'Local user path in {relative}')
            if re.search(r'\b(?:hf_|gh[pousr]_)[A-Za-z0-9]{30,}', content):
                raise ValueError(f'Possible credential in {relative}')
        selected[relative.as_posix()] = data
    missing = REQUIRED - selected.keys()
    if missing:
        raise ValueError(f'Missing required release files: {sorted(missing)}')
    if not selected['Start Voice Studio.exe'].startswith(b'MZ'):
        raise ValueError('Missing Windows launcher executable')
    if not selected['START HERE.txt'].decode('utf-8-sig').startswith('王洪文'):
        raise ValueError('Quickstart must put Chinese first')
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / 'Wang-Hongwen-Voice-Studio-Windows.zip'
    # Lossless ZIP compression preserves every extracted byte. Fixed headers
    # are deterministic with the same Python/zlib build. Model weights are excluded.
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as result:
        for name, data in sorted(selected.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            result.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None or set(check.namelist()) != selected.keys():
            raise ValueError('Archive integrity check failed')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(
        f'{checksum}  {archive.name}\n', encoding='utf-8', newline='\n')
    return {'file': str(archive), 'bytes': archive.stat().st_size,
            'sha256': checksum, 'files': len(selected)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('dist'))
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parent.parent, args.output_dir),
                     ensure_ascii=False, indent=2))
