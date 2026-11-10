"""Restore byte-identical WAV references from a lossless Windows download bundle."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def restore(root: Path, ffmpeg: str) -> int:
    assets = root / 'assets'
    manifest = assets / 'packed-references.json'
    if not manifest.exists():
        return 0  # Source/Docker deployments use the original WAV files.
    restored = 0
    for item in json.loads(manifest.read_text(encoding='utf-8'))['files']:
        for name in (item['wav'], item['flac']):
            if Path(name).name != name or '/' in name or '\\' in name:
                raise ValueError('Invalid reference filename')
        target, packed = assets / item['wav'], assets / item['flac']
        if target.is_symlink() or packed.is_symlink():
            raise ValueError('Linked reference rejected')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']:
            continue
        if not packed.exists():
            raise FileNotFoundError('Reference missing. Extract the complete Windows ZIP again.')
        if hashlib.sha256(packed.read_bytes()).hexdigest() != item['flac_sha256']:
            raise ValueError('Packed reference checksum mismatch')
        result = subprocess.run(
            [ffmpeg, '-v', 'error', '-i', str(packed), '-map', '0:a:0',
             '-f', item['raw_format'], '-acodec', item['pcm_codec'], '-'],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if len(result.stdout) != item['pcm_bytes']:
            raise ValueError('Reference sample count mismatch')
        data = base64.b64decode(item['prefix']) + result.stdout + base64.b64decode(item['suffix'])
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Restored reference checksum mismatch')
        descriptor, name = tempfile.mkstemp(prefix='.restore-', dir=assets)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
        restored += 1
    return restored


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--ffmpeg', default=os.getenv('FFMPEG', 'ffmpeg'))
    args = parser.parse_args()
    print(json.dumps({'restored': restore(args.root, args.ffmpeg)}))
