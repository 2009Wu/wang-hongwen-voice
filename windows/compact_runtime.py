"""Remove build-only files from the launcher's private inference runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
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


def compact(root: Path, dry_run: bool = False) -> dict:
    root = root.absolute()
    runtime = root / '.runtime'
    candidates = []
    libraries = runtime / 'python/tools/Lib/site-packages/torch/lib'
    if plain_path(libraries, root) and libraries.is_dir():
        candidates.extend(libraries.glob('*.lib'))
    ffmpeg = runtime / 'ffmpeg'
    if plain_path(ffmpeg, root) and ffmpeg.is_dir():
        # The pinned bundle has exactly one version directory. No recursive walk.
        candidates.extend(ffmpeg.glob('*/bin/ffplay.exe'))
        candidates.append(ffmpeg / 'bin/ffplay.exe')
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
    return {'bytes': total, 'dry_run': dry_run, 'removed': removed, 'skipped': skipped}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    print(json.dumps(compact(args.root, args.dry_run), ensure_ascii=False))
