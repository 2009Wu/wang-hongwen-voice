"""Use archived stems to preview or export a new mix without loading models."""
from pathlib import Path
import math

from studio_library import get_record, workspace_for
from studio_paths import EXPORTS, copy_owned, owned_path, read_json, atomic_json

STEMS = ('lead-processed.wav', 'source.wav', 'instrumental.wav')
ARCHIVE_STEMS = (*STEMS, 'model-voice.wav', 'reference.wav')


def mix_request(identifier, vocals, backing, *, preview=False, start=0):
    record = get_record(identifier)
    if record['status'] != 'completed' or record['mode'] != 'sing' or record.get('preview'):
        raise ValueError('请先载入一首完整翻唱。')
    directory = workspace_for(identifier)
    if not all((directory / filename).is_file() for filename in STEMS):
        raise ValueError('这份作品的分轨已清理，请重新生成翻唱。')
    vocals, backing, start = float(vocals), float(backing), float(start)
    if not (-12 <= vocals <= 9 and -15 <= backing <= 6 and math.isfinite(start) and start >= 0):
        raise ValueError('混音音量或试听起点无效。')
    request = dict(read_json(directory / 'request.json', {}))
    for key in ('redo_start', 'redo_end', 'approved_preview_id', 'input', 'reference_input', 'input_sha256'):
        request.pop(key, None)
    request.update(operation='mix_preview' if preview else 'remix', mode='sing', parent_id=identifier,
                   preview=False, vocal_db=vocals, music_db=backing, mix_start=start)
    return request


def render_mix(request, job):
    import soundfile as sf
    from audio_utils import export_flac, export_mp3, export_video_copy, master, mix_tracks

    parent = request['parent_id']
    preview = request['operation'] == 'mix_preview'
    request = mix_request(parent, request['vocal_db'], request['music_db'], preview=preview,
                          start=request.get('mix_start', 0))
    workspace = workspace_for(parent)
    base = get_record(parent)['result']
    inputs = [owned_path(workspace, name, must_exist=True) for name in STEMS]
    first = sf.info(inputs[0])
    start = round(request['mix_start'] * first.samplerate) if preview else 0
    if not 0 <= start < first.frames:
        raise ValueError('试听起点超出歌曲时长。')
    # Keep a little context around the preview for the backing-track dynamics.
    context = max(0, start - first.samplerate)
    count = min(first.frames - context, start - context + 12 * first.samplerate) if preview else -1
    (voice, rate), (source, source_rate), (music, music_rate) = [
        sf.read(path, start=context, frames=count, dtype='float32', always_2d=index == 2)
        for index, path in enumerate(inputs)
    ]
    if rate != source_rate or rate != music_rate or voice.ndim != 1 or source.ndim != 1:
        raise ValueError('分轨格式不一致，请重新生成翻唱。')
    signal = mix_tracks(voice, source, music, rate, request['vocal_db'], request['music_db'])
    outputs = job / 'results'
    outputs.mkdir()
    if preview:
        import numpy as np
        signal = signal[start - context:]
        peak = float(np.max(np.abs(signal), initial=0))
        if peak > .90:
            signal *= .90 / peak
        path = outputs / 'mix-preview.wav'
        sf.write(path, signal, rate, subtype='PCM_16')
        return {'audio': str(path), 'wav': str(path), 'flac': None, 'video': None, 'details': None, 'reference': None}

    intermediate = job / 'mix.wav'
    sf.write(intermediate, signal, rate, subtype='FLOAT')
    wav = outputs / 'AI-cover-remix.wav'
    master(intermediate, wav, rate=rate)
    mp3, flac = wav.with_suffix('.mp3'), wav.with_suffix('.flac')
    export_mp3(wav, mp3)
    export_flac(wav, flac)
    video = None
    if base.get('video'):
        original_video = owned_path(EXPORTS, base['video'])
        if original_video.is_file():
            video = wav.with_suffix('.mp4')
            export_video_copy(original_video, wav, video)
    for name in ARCHIVE_STEMS:
        original = owned_path(workspace, name)
        if original.is_file():
            copy_owned(original, job / name, link=True)
    details = dict(read_json(owned_path(EXPORTS, base['details']), {})) if base.get('details') else {}
    details.update(remixed=True, parent_id=parent, vocal_gain_db=request['vocal_db'],
                   instrumental_gain_db=request['music_db'], redo_interval_seconds=None)
    metadata = outputs / 'generation.json'
    atomic_json(metadata, details)
    return {'audio': str(mp3), 'wav': str(wav), 'flac': str(flac), 'video': str(video) if video else None,
            'details': str(metadata), 'reference': None}
