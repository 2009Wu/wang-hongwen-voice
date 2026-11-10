"""Remove build-only files from the launcher's private inference runtime."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat


def plain_path(path: Path, root: Path) -> bool:
    """Do not follow junctions/symlinks in any component of the app path."""
    path.absolute().relative_to(root.absolute())
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                return False
        if item == root.absolute():
            break
    return True


def compact(root: Path, dry_run: bool = False, once: bool = False) -> dict:
    root = root.absolute()
    runtime = root / '.runtime'
    marker = runtime / 'compact-runtime-v2.json'
    if once and plain_path(marker, root) and marker.is_file():
        return {'bytes': 0, 'dry_run': dry_run, 'removed': [], 'skipped': [], 'already_done': True}
    candidates = []
    libraries = runtime / 'python/tools/Lib/site-packages/torch/lib'
    if plain_path(libraries, root) and libraries.is_dir():
        candidates.extend(libraries.glob('*.lib'))
    ffmpeg = runtime / 'ffmpeg'
    if plain_path(ffmpeg, root) and ffmpeg.is_dir():
        # The pinned bundle has exactly one version directory. No recursive walk.
        candidates.extend(ffmpeg.glob('*/bin/ffplay.exe'))
        candidates.append(ffmpeg / 'bin/ffplay.exe')
    # Only development headers, an unused upstream demo UI and tool manuals.
    # The app's served UI lives in .runtime/ui and is never trimmed here.
    folders = [runtime / 'python/tools/Lib/site-packages/torch/include',
               runtime / 'speech/Lib/site-packages/gradio/templates/frontend',
               runtime / 'speech/Lib/site-packages/gradio/templates/node']
    if plain_path(ffmpeg, root) and ffmpeg.is_dir():
        folders.extend(ffmpeg.glob('*/doc'))
    for folder in folders:
        if not plain_path(folder, root) or not folder.is_dir():
            continue
        for current, directories, files in os.walk(folder, followlinks=False):
            directories[:] = [name for name in directories if plain_path(Path(current) / name, root)]
            for name in files:
                if not re.search(r'licen[sc]e|notice|copying|copyright', name, re.IGNORECASE):
                    candidates.append(Path(current) / name)
    removed, skipped, total = [], [], 0
    for path in sorted(set(candidates)):
        if not plain_path(path, root) or not path.is_file():
            continue
        try:
            size = path.stat().st_size
            if not dry_run:
                path.unlink()
            total += size
            removed.append(path.relative_to(root).as_posix())
        except OSError as error:
            skipped.append({'file': path.relative_to(root).as_posix(), 'error': str(error)})
    result = {'bytes': total, 'dry_run': dry_run, 'removed': removed, 'skipped': skipped}
    if not dry_run and not skipped and plain_path(marker, root) and runtime.is_dir():
        marker.write_text(json.dumps({'policy': 2, 'bytes': total, 'files': len(removed)}) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--once', action='store_true', help='Skip scans already completed by setup/startup')
    args = parser.parse_args()
    result = compact(args.root, args.dry_run, args.once)
    print(json.dumps({'bytes': result['bytes'], 'removed_files': len(result['removed']),
                      'skipped_files': len(result['skipped']), 'already_done': result.get('already_done', False)}))
