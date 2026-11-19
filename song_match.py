"""Local fingerprint matching against a short catalog of public recordings."""
from base64 import b64decode, b64encode
import json
import os
from pathlib import Path
import subprocess
import zlib

import numpy as np

RATE = 11025
WINDOW = 4096
HOP = 1024
FEATURES = 24
MIN_OVERLAP = 140
MAX_SHIFT = 32
FORMATS = 'mov,mp3,wav,flac,ogg,aac,matroska,webm,avi'


def fingerprint(path):
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([os.getenv('FFMPEG', 'ffmpeg'), '-v', 'error', '-nostdin',
                             '-protocol_whitelist', 'file,pipe', '-format_whitelist', FORMATS,
                             '-i', str(path), '-t', '33', '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(RATE),
                             '-f', 's16le', 'pipe:1'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=True, timeout=20, **options)
    samples = np.frombuffer(result.stdout, dtype='<i2').astype(np.float32)
    if len(samples) < WINDOW + MIN_OVERLAP * HOP:
        return np.empty((0, FEATURES), dtype=np.uint8)
    frames = np.lib.stride_tricks.sliding_window_view(samples, WINDOW)[::HOP]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(WINDOW), axis=1))
    frequencies = np.fft.rfftfreq(WINDOW, 1 / RATE)
    audible = (frequencies >= 65) & (frequencies < 4700)
    f = frequencies[audible]
    weights = np.sqrt(spectrum[:, audible])
    pitch = np.rint(69 + 12 * np.log2(f / 440)).astype(int) % 12
    octave_bands = np.minimum(np.searchsorted(np.geomspace(65, 4700, 13), f, side='right') - 1, 11)
    chroma = np.stack([np.bincount(pitch, row, minlength=12) for row in weights])
    spectrum_bands = np.stack([np.bincount(octave_bands, row, minlength=12) for row in weights])
    features = np.concatenate([
        np.sqrt(array / np.maximum(array.sum(axis=1, keepdims=True), 1))
        for array in (chroma, spectrum_bands)
    ], axis=1)
    return np.rint(np.clip(features, 0, 1) * 255).astype(np.uint8)


def encode(features):
    return b64encode(zlib.compress(features.tobytes(), level=9)).decode('ascii')


def similarity(first, second):
    first = first.astype(np.float32) / 255
    second = second.astype(np.float32) / 255
    best = 0.0
    for shift in range(-MAX_SHIFT, MAX_SHIFT + 1):
        a, b = first[max(shift, 0):], second[max(-shift, 0):]
        length = min(len(a), len(b))
        if length < MIN_OVERLAP:
            continue
        a, b = a[:length], b[:length]
        # Subtract the time-averaged spectrum to distinguish different arrangements.
        a, b = a - a.mean(axis=0), b - b.mean(axis=0)
        normal = np.sqrt(np.sum(a * a) * np.sum(b * b))
        if normal > .01:
            best = max(best, float(np.sum(a * b) / normal))
    return best


def match(path, catalog_path):
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    if not catalog:
        return None
    query = fingerprint(path)
    if not query.size:
        return None
    scores = []
    for song_id, item in catalog.items():
        data = zlib.decompress(b64decode(item['fingerprint'], validate=True))
        reference = np.frombuffer(data, dtype=np.uint8).reshape(-1, FEATURES)
        scores.append((similarity(query, reference), song_id))
    scores.sort(reverse=True)
    score, song_id = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0
    return song_id if score >= .87 and score - second >= .12 else None
