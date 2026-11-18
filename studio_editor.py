"""Waveform data and same-time audition for completed song covers."""
import math
import wave
from html import escape
from urllib.parse import quote

import numpy as np

from studio_library import get_record
from studio_paths import EXPORTS, owned_path


def waveform(path, bars=192):
    with wave.open(str(path), 'rb') as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        width = audio.getsampwidth()
        if not frames or rate <= 0:
            raise ValueError('作品音频为空。')
        block = max(1, math.ceil(frames / bars))
        peaks = []
        for _ in range(min(bars, math.ceil(frames / block))):
            data = audio.readframes(block)
            if width == 3:
                # The high 16 bits preserve enough detail for an overview.
                values = np.frombuffer(data, dtype='uint8').reshape(-1, 3)[:, 1:]
                samples = np.ascontiguousarray(values).view('<i2')
            elif width == 1:
                samples = np.frombuffer(data, dtype='uint8').astype('int16') - 128
            else:
                samples = np.frombuffer(data, dtype=f'<i{width}')
            scale = 32768 if width == 3 else 2 ** (width * 8 - 1)
            peak = np.max(np.abs(samples.astype('float64')), initial=0) / scale
            peaks.append(round(peak * 100))
        return frames / rate, peaks


def result_wav(result):
    return owned_path(EXPORTS, result['wav'], must_exist=True)


def media_url(path):
    return 'gradio_api/file=' + quote(path.as_posix(), safe='/')


def editable_markup(result, candidate=None, selection=None):
    if not result or not result.get('history_id') or not result.get('wav'):
        return ''
    record = get_record(result['history_id'])
    if record.get('mode') != 'sing' or record.get('preview') or record.get('status') != 'completed':
        return ''
    source = result_wav(result)
    length, peaks = waveform(source)
    start, end = selection or (0, min(10, length))
    attrs = {
        'a': media_url(source),
        'b': media_url(result_wav(candidate)) if candidate else '',
        'length': length,
        'peaks': ','.join(map(str, peaks)),
        'start': start,
        'end': end,
    }
    data = ' '.join(f'data-{key}="{escape(str(value), quote=True)}"' for key, value in attrs.items())
    return f'''<div class="studio-wave-editor" {data}>
  <p data-copy="hint">拖动波形选段，也可以输入起止秒数。</p>
  <canvas aria-hidden="true" width="540" height="86"></canvas>
  <div class="studio-wave-controls">
    <label><span data-copy="start">起点（秒）</span> <input type="number" min="0" max="{length}" step="any" data-range="start"></label>
    <label><span data-copy="end">终点（秒）</span> <input type="number" min="0" max="{length}" step="any" data-range="end"></label>
    <div class="studio-wave-versions" {'hidden' if not candidate else ''}>
      <button type="button" data-version="a" aria-pressed="true" data-copy="original">A · 原版</button>
      <button type="button" data-version="b" aria-pressed="false" data-copy="candidate">B · 重做版</button>
    </div>
  </div>
  <audio controls preload="metadata" aria-label="试听所选片段"></audio>
</div>'''

