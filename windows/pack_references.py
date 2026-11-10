"""Rebuild the lossless reference payloads before packaging a Windows release."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess


def pack(root: Path, ffmpeg: str):
    items = []
    for wav in sorted((root / 'assets').glob('*-reference.wav')):
        data = wav.read_bytes()
        if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
            raise ValueError('Expected RIFF WAV reference')
        offset, fmt = 12, None
        while offset + 8 <= len(data):
            tag = data[offset:offset + 4]
            size = struct.unpack_from('<I', data, offset + 4)[0]
            if tag == b'fmt ':
                fmt = struct.unpack_from('<HHIIHH', data, offset + 8)
            if tag == b'data':
                start, length = offset + 8, size
                break
            offset += 8 + size + size % 2
        else:
            raise ValueError('Missing WAV PCM data')
        if not fmt or fmt[0] not in (1, 65534) or fmt[5] not in (16, 24):
            raise ValueError('Expected 16/24-bit integer PCM')
        bits = fmt[5]
        flac = wav.with_suffix('.flac')
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(wav), '-map_metadata', '-1',
                        '-c:a', 'flac', '-compression_level', '12', str(flac)], check=True)
        items.append(dict(wav=wav.name, flac=flac.name,
                          sha256=hashlib.sha256(data).hexdigest(),
                          flac_sha256=hashlib.sha256(flac.read_bytes()).hexdigest(),
                          prefix=base64.b64encode(data[:start]).decode(),
                          suffix=base64.b64encode(data[start + length:]).decode(),
                          pcm_bytes=length, raw_format=f's{bits}le', pcm_codec=f'pcm_s{bits}le'))
    if len(items) != 2:
        raise ValueError('Both original WAV references are required')
    (root / 'assets/packed-references.json').write_text(
        json.dumps({'files': items}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default=os.getenv('FFMPEG', 'ffmpeg'))
    args = parser.parse_args()
    pack(Path(__file__).resolve().parent.parent, args.ffmpeg)
