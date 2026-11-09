"""Media validation, exact-length overlap-add, and the approved vocal mix."""
import json
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d

FORMATS = "mov,mp3,wav,flac,ogg,aac,matroska,webm,avi"
COMMENT = "AI-generated Wang Hongwen reference voice; not an authentic recording or performance."


def ffmpeg(args, timeout=900):
    command = [os.getenv("FFMPEG", "ffmpeg"), "-hide_banner", "-nostdin", "-y", *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError("Audio/video processing failed: " + result.stderr[-1500:])
    return result


def probe(path):
    result = subprocess.run([
        os.getenv("FFPROBE", "ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe",
        "-format_whitelist", FORMATS, "-show_format", "-show_streams", "-of", "json", str(path),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode:
        raise ValueError("This file cannot be read as audio/video. Try MP3, WAV, FLAC, M4A, OGG, or MP4.")
    data = json.loads(result.stdout)
    if not any(s.get("codec_type") == "audio" for s in data.get("streams", [])):
        raise ValueError("The uploaded file has no audio track.")
    return data


def decode_input(path, destination, max_seconds, max_mb):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > max_mb * 1024**2:
        raise ValueError(f"Upload a file smaller than {max_mb} MB.")
    data = probe(path)
    duration = float(data.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("The file must have a measurable duration.")
    if duration > max_seconds + .05:
        raise ValueError(f"The song limit is {max_seconds // 60} minutes. Trim the file first.")
    ffmpeg(["-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS,
            "-i", path, "-t", str(max_seconds + 1), "-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100",
            "-c:a", "pcm_f32le", destination])
    audio, rate = sf.read(destination, dtype="float32", always_2d=True)
    if not np.isfinite(audio).all() or len(audio) < rate:
        raise ValueError("The file must contain at least one second of finite audio.")
    if len(audio) / rate > max_seconds + .05:
        raise ValueError("The decoded audio exceeds the song limit.")
    if float(np.max(np.abs(audio))) < 1e-5:
        raise ValueError("This file contains only silence.")
    return data, len(audio), rate


def windows(total, size, overlap):
    if total <= 0 or size <= overlap or overlap < 0:
        raise ValueError("Invalid chunk dimensions")
    start = 0
    while start < total:
        end = min(start + size, total)
        yield start, end
        if end == total:
            break
        start = end - overlap


def fade_weights(length, overlap, first, last):
    result = np.ones(length, dtype="float32")
    n = min(length, overlap)
    if n and not first:
        result[:n] *= np.linspace(0, 1, n, endpoint=False)
    if n and not last:
        result[-n:] *= np.linspace(1, 0, n, endpoint=False)
    return result


def envelope(audio, rate, seconds=.05):
    return np.sqrt(np.maximum(uniform_filter1d(np.asarray(audio, dtype="float64") ** 2, max(1, int(rate * seconds))), 1e-12))


def restore_dynamics(voice, source, rate):
    source_env, voice_env = envelope(source, rate), envelope(voice, rate)
    gain = uniform_filter1d(np.clip(source_env / np.maximum(voice_env, .002), .15, 3), max(1, int(rate * .08)))
    gate = uniform_filter1d(np.clip((source_env - .0015) / .006, 0, 1), max(1, int(rate * .025)))
    return (voice * gain * gate).astype("float32")


def mix_tracks(voice, source, music, rate, vocal_db=4.5, music_db=-1.5):
    if len(voice) != len(source) or len(voice) != len(music):
        raise ValueError("Stem lengths do not match")
    activity = uniform_filter1d(np.clip((envelope(source, rate, .08) - .005) / .04, 0, 1), max(1, int(rate * .18)))
    backing = music * (10 ** ((music_db - activity) / 20))[:, None]
    mix = backing + (voice * 10 ** (vocal_db / 20))[:, None]
    if not np.isfinite(mix).all():
        raise ValueError("The generated mix contains invalid samples")
    return mix.astype("float32")


def master(source, output, rate=44100, target=-14):
    base = f"loudnorm=I={target}:TP=-1.5:LRA=11"
    analysis = ffmpeg(["-i", source, "-af", base + ":print_format=json", "-f", "null", "-"])
    stats = json.loads(re.findall(r'\{\s*"input_i"[\s\S]+?\}', analysis.stderr)[-1])
    if not all(math.isfinite(float(stats[k])) for k in ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]):
        raise ValueError("The generated audio is silent; try a different section or text.")
    filt = (base + f':measured_I={stats["input_i"]}:measured_TP={stats["input_tp"]}'
            f':measured_LRA={stats["input_lra"]}:measured_thresh={stats["input_thresh"]}'
            f':offset={stats["target_offset"]}:linear=true')
    ffmpeg(["-v", "error", "-i", source, "-af", filt, "-ar", str(rate), "-c:a", "pcm_s24le",
            "-metadata", "comment=" + COMMENT, output])


def export_mp3(wav, output):
    ffmpeg(["-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "320k", "-metadata", "comment=" + COMMENT, output])


def export_flac(wav, output):
    """Lossless compression of the exact mastered 24-bit PCM samples."""
    ffmpeg(["-v", "error", "-i", wav, "-c:a", "flac", "-compression_level", "8",
            "-metadata", "comment=" + COMMENT, output])


def export_video(source, wav, output):
    # Keep the first video stream and replace all original audio. No GPU encoder required.
    ffmpeg(["-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-i", source,
            "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-vf", "scale=720:-2,fps=30", "-c:v", "libx264",
            "-preset", "fast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
            "-metadata", "comment=" + COMMENT, "-movflags", "+faststart", "-shortest", output], timeout=1800)


def split_text(text, limit=100):
    """Bounded speech chunks, preserving every character and punctuation."""
    text = text.strip()
    if not text:
        raise ValueError("Enter some text first.")
    parts = re.findall(r'[^。！？!?\n]+[。！？!?\n]*|[。！？!?\n]+', text)
    result, current = [], ""
    for part in parts:
        while part:
            room = limit - len(current)
            current += part[:room]
            part = part[room:]
            if len(current) == limit:
                result.append(current)
                current = ""
        if current and len(current) > limit // 2:
            result.append(current)
            current = ""
    if current:
        result.append(current)
    return result
