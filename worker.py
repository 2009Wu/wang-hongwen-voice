"""Separate GPU process for each job; exiting releases all model memory."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from settings import ASSETS, CACHE, LANGUAGES, MAX_MB, MAX_SECONDS, MAX_TEXT


def emit(fraction, message):
    print("@@PROGRESS " + json.dumps({"fraction": fraction, "message": message}), flush=True)


def prepare_environment():
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, suffix in [("HF_HOME", "huggingface"), ("TORCH_HOME", "torch"), ("NUMBA_CACHE_DIR", "numba")]:
        os.environ.setdefault(name, str(CACHE / suffix))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    torch.set_num_threads(int(os.getenv("CPU_THREADS", "4")))
    if not torch.cuda.is_available():
        if os.getenv("VOICE_STUDIO_DESKTOP") == "1":
            raise RuntimeError("A CUDA GPU is required. Update the NVIDIA driver and use Repair setup in the launcher.")
        raise RuntimeError("A CUDA GPU is required. Select GPU hardware in the Space Settings and restart.")
    torch.manual_seed(42)


def separate(source_path, job, policy):
    import gc
    import torch
    import numpy as np
    import soundfile as sf
    from demucs.api import Separator
    emit(.08, "正在分离人声和伴奏…")
    separator = Separator(model="htdemucs", device="cpu" if policy["profile"] == "low" else "cuda", shifts=1, progress=False)
    _, stems = separator.separate_audio_file(source_path)
    vocals = stems["vocals"].cpu().numpy().T
    music = sum(v for k, v in stems.items() if k != "vocals").cpu().numpy().T
    sf.write(job / "original-vocals.wav", vocals, 44100, subtype="FLOAT")
    sf.write(job / "instrumental.wav", music, 44100, subtype="FLOAT")
    del separator, stems
    gc.collect()
    torch.cuda.empty_cache()
    return vocals.mean(axis=1).astype("float32"), music.astype("float32")


def sing(request, job):
    import numpy as np
    import soundfile as sf
    import torch
    from audio_utils import decode_input, windows, fade_weights, restore_dynamics, ffmpeg, mix_tracks, master, export_mp3, export_video
    source_path = Path(request["input"])
    vocal_db = float(request.get("vocal_db", 4.5))
    music_db = float(request.get("music_db", -1.5))
    steps = int(request.get("steps", 40))
    if not (-2 <= vocal_db <= 9 and -12 <= music_db <= 3 and steps in [20, 40, 60]):
        raise ValueError("Invalid conversion settings")
    emit(.02, "正在读取歌曲…")
    metadata, samples, rate = decode_input(source_path, job / "input.wav", MAX_SECONDS, MAX_MB)
    source, music = separate(job / "input.wav", job, request["_policy"])
    if len(source) != samples:
        raise RuntimeError("The separator changed the audio length")
    emit(.25, "正在载入翻唱模型（首次使用需下载）…")
    repo = ROOT / "vendor" / "seed_vc"
    sys.path.insert(0, str(repo))
    os.chdir(repo)
    import inference
    # The vendored cache paths are patched to honor HF_HOME. Override only for local tests.
    args = SimpleNamespace(source="", target=str(ASSETS / "singing-reference.wav"), output=str(job),
                           diffusion_steps=steps, length_adjust=1.0, inference_cfg_rate=.7,
                           f0_condition=True, auto_f0_adjust=False, semi_tone_shift=0,
                           checkpoint=os.getenv("SEED_CHECKPOINT"), config=os.getenv("SEED_CONFIG"), fp16=True,
                           low_vram=request["_policy"]["profile"] != "fast")
    models = inference.load_models(args)
    inference.load_models = lambda _: models
    combined, weights = np.zeros(samples, dtype="float32"), np.zeros(samples, dtype="float32")
    chunks = list(windows(samples, rate * 40, int(rate * .5)))
    for i, (start, end) in enumerate(chunks):
        emit(.3 + .51 * i / len(chunks), f"正在翻唱 {i + 1}/{len(chunks)} · {start / rate:.0f}–{end / rate:.0f} 秒")
        chunk = source[start:end]
        if np.sqrt(np.mean(chunk.astype("float64") ** 2)) < .001:
            voice = np.zeros(len(chunk), dtype="float32")
        else:
            args.source = str(job / f"chunk-{i:03}.wav")
            sf.write(args.source, chunk, rate, subtype="FLOAT")
            torch.manual_seed(42)
            inference.main(args)
            out = job / f"vc_chunk-{i:03}_singing-reference_1.0_{steps}_0.7.wav"
            voice, out_rate = sf.read(out, dtype="float32")
            if out_rate != rate or voice.ndim != 1 or not np.isfinite(voice).all():
                raise RuntimeError("Invalid audio returned by the singing model")
            voice = np.pad(voice[:len(chunk)], (0, max(0, len(chunk) - len(voice))))
        fade = fade_weights(len(chunk), int(rate * .5), i == 0, i == len(chunks) - 1)
        combined[start:end] += voice * fade
        weights[start:end] += fade
    voice = restore_dynamics(combined / np.maximum(weights, 1e-6), source, rate)
    sf.write(job / "lead-raw.wav", voice, rate, subtype="FLOAT")
    emit(.84, "正在提升人声清晰度并平衡伴奏…")
    lead_path = job / "lead-processed.wav"
    ffmpeg(["-v", "error", "-i", job / "lead-raw.wav", "-af",
            "highpass=f=70,equalizer=f=300:t=q:w=1:g=-1,equalizer=f=2800:t=q:w=1:g=1.5,acompressor=threshold=0.125:ratio=2:attack=8:release=100:makeup=1.1",
            "-c:a", "pcm_f32le", lead_path])
    voice, _ = sf.read(lead_path, dtype="float32")
    sf.write(job / "mix.wav", mix_tracks(voice, source, music, rate, vocal_db, music_db), rate, subtype="FLOAT")
    public = job / "results"
    public.mkdir(exist_ok=True)
    wav, mp3 = public / "Wang-Hongwen-AI-cover.wav", public / "Wang-Hongwen-AI-cover.mp3"
    emit(.88, "正在处理响度并导出音频…")
    master(job / "mix.wav", wav)
    export_mp3(wav, mp3)
    from audio_utils import export_flac
    flac = wav.with_suffix(".flac")
    export_flac(wav, flac)
    video = None
    if request.get("video", True) and any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in metadata["streams"]):
        emit(.93, "正在合成翻唱视频…")
        video = public / "Wang-Hongwen-AI-cover.mp4"
        export_video(source_path, wav, video)
    details = {"ai_generated": True, "engine": "Seed-VC reference-only", "speaker_finetuning": False,
               "pitch_shift_semitones": 0, "steps": steps, "vocal_gain_db": vocal_db, "instrumental_gain_db": music_db,
               "instrumental_duck_db": 1, "duration_seconds": samples / rate, "reference": "singing-reference.wav",
               "sample_rate": rate, "master_lufs_target": -14}
    (public / "generation.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    return {"audio": str(mp3), "wav": str(wav), "flac": str(flac), "video": str(video) if video else None, "details": str(public / "generation.json")}


def speak(request, job):
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel
    from audio_utils import split_text, master, export_mp3
    text = str(request.get("text", "")).strip()
    language = request.get("language", "Chinese")
    if not text or len(text) > MAX_TEXT or language not in LANGUAGES:
        raise ValueError(f"Enter 1–{MAX_TEXT} characters and choose a supported language.")
    emit(.04, "正在载入语音模型（首次使用需下载）…")
    manifest = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    # Hub 0.36's first symlink-support probe is not thread-safe on Windows.
    # Download serially so normal users use the supported file-copy fallback.
    model_path = snapshot_download(manifest["tts"]["repo"], revision=manifest["tts"]["revision"],
                                   max_workers=1 if os.name == "nt" else 8)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = Qwen3TTSModel.from_pretrained(model_path, device_map="cuda:0", dtype=dtype, attn_implementation="sdpa")
    reference = json.loads((ASSETS / "reference.json").read_text(encoding="utf-8"))
    prompt = model.create_voice_clone_prompt(ref_audio=str(ASSETS / "speech-reference.wav"),
                                            ref_text=reference["speech_transcript"], x_vector_only_mode=False)
    chunks = split_text(text)
    audio = []
    rate = None
    for i, part in enumerate(chunks):
        emit(.2 + .65 * i / len(chunks), f"正在朗读 {i + 1}/{len(chunks)}…")
        torch.manual_seed(42 + i)
        waves, rate = model.generate_voice_clone(text=part, language=language, voice_clone_prompt=prompt,
                                                 max_new_tokens=1536)
        wave = np.asarray(waves[0], dtype="float32").reshape(-1)
        if not len(wave) or not np.isfinite(wave).all():
            raise RuntimeError("The speech model returned invalid audio")
        # A full token budget usually indicates truncation: don't silently return missing words.
        if len(wave) / rate >= 125:
            raise RuntimeError("This sentence took too long to read. Use shorter sentences and try again.")
        if audio:
            audio.append(np.zeros(int(rate * .18), dtype="float32"))
        audio.append(wave)
    raw = job / "speech-raw.wav"
    sf.write(raw, np.concatenate(audio), rate, subtype="FLOAT")
    public = job / "results"
    public.mkdir(exist_ok=True)
    wav, mp3 = public / "Wang-Hongwen-AI-speech.wav", public / "Wang-Hongwen-AI-speech.mp3"
    emit(.9, "正在导出语音…")
    master(raw, wav, rate=rate, target=-16)
    export_mp3(wav, mp3)
    from audio_utils import export_flac
    flac = wav.with_suffix(".flac")
    export_flac(wav, flac)
    details = {"ai_generated": True, "engine": manifest["tts"]["repo"], "language": language,
               "characters": len(text), "chunks": len(chunks), "sample_rate": rate}
    (public / "generation.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    return {"audio": str(mp3), "wav": str(wav), "flac": str(flac), "video": None, "details": str(public / "generation.json")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    job = args.request.resolve().parent
    prepare_environment()
    from performance import configure, memory_report
    request["_policy"] = configure(request)
    emit(.01, "自动性能档位：" + request["_policy"]["label"])
    started = time.monotonic()
    result = sing(request, job) if request["mode"] == "sing" else speak(request, job)
    result["elapsed_seconds"] = round(time.monotonic() - started, 1)
    details_path = Path(result["details"])
    details = json.loads(details_path.read_text(encoding="utf-8"))
    details["performance"] = memory_report(request["_policy"])
    details["elapsed_seconds"] = result["elapsed_seconds"]
    details_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    (job / "result.json").write_text(json.dumps(result), encoding="utf-8")
    emit(1, "已完成 · AI 生成音频")


if __name__ == "__main__":
    main()
