---
title: Wang Hongwen Voice Studio
emoji: 🎙️
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
license: gpl-3.0
short_description: AI singing covers and text to speech
tags:
  - audio
  - voice-conversion
  - text-to-speech
  - gradio
models:
  - Plachta/Seed-VC
  - Qwen/Qwen3-TTS-12Hz-0.6B-Base
---

# Wang Hongwen Voice Studio · 王洪文语音工作室

Upload a song to create an AI singing cover, or enter text to generate speech using the bundled archival Wang Hongwen voice reference. The interface clearly labels outputs as AI-generated.

The singing defaults reproduce the reference-only workflow selected for the approved cover: original pitch and melody, 40 diffusion steps, 20-second speech prompt, gentle vocal EQ/compression, +4.5 dB lead, −1.5 dB instrumental, and 1 dB of extra backing reduction during vocals. This is a reference-conditioned app, not a separately trained Wang Hongwen checkpoint. Similarity depends on the input and the archival reference.

## Publish the source for free

You can share this project's source code without paying to host audio generation. Create a public **Static → Blank Space** and use the separate static publication package supplied with this release. It contains a project page, downloadable source ZIP, reference audio, and a synthetic speech sample. Visitors download the app and run generation on their own CUDA GPU. The static page itself does not perform conversion.

Alternatively, publish this folder as a public source repository on GitHub.

## Run the app on Hugging Face GPU hardware

Hugging Face currently requires a paid plan to create regular Docker/Gradio Spaces, with GPU hardware billed separately. A paid plan is unnecessary for the static source-publication option above. See the [Spaces overview](https://huggingface.co/docs/hub/spaces-overview).

1. Extract the ZIP on your computer.
2. [Create a Space](https://huggingface.co/new-space). Choose **Docker → Blank** as the SDK/template. Choose visibility as desired.
3. Upload the **contents of this folder** to the repository root. `Dockerfile`, `app.py`, `README.md`, `assets/`, and `vendor/` must be at the top level. Preserve the nested folders; do not upload only the ZIP.
4. In **Settings → Hardware**, select a CUDA GPU with **at least 16 GB VRAM**. A T4 16 GB is a starting point; an L4/A10G provides more headroom. GPU hardware is billed by Hugging Face. This is a regular GPU Docker Space, not a ZeroGPU Space.
5. Wait for the image build, then open **App**. The first generation downloads several GB of public model weights. Later jobs reuse the local cache while the Space stays running. No API key or gated-model approval is required by the default public model repositories.

The web interface starts without loading models. A CPU-only Space can show the interface, but generation explains that GPU hardware is required. This package does not change your hardware or subscribe you to a paid service.

Hugging Face's [Docker Space documentation](https://huggingface.co/docs/hub/spaces-sdks-docker) covers port 7860 and user ID 1000. Both are configured here. If you use git rather than the web uploader, install Git LFS before committing the two WAV reference files (`.gitattributes` is included).

## Use the app

**Sing a song:** Upload MP3, WAV, M4A, MP4, FLAC, OGG, MOV, AAC, MKV, or WebM containing an existing vocal performance. Click **Create AI cover**. Download the stereo WAV, 320 kbps MP3, and optionally an MP4 with the replaced audio. The backing track is separated automatically; residual original vocals may remain in difficult mixes. Instrumental-only input does not invent a melody or lyrics.

**Text to speech:** Enter text, choose a language, and click **Generate speech**. Chinese is the closest match to the reference. Qwen supports Chinese, English, Japanese, Korean, French, German, Spanish, Portuguese, Italian, and Russian; Auto is also available. Long text is split into bounded chunks. Download WAV or MP3.

**Stop** cancels that queued/running generation. Both tabs share a single GPU queue. Each job runs in a fresh process and releases its models when it exits. Save downloads promptly; they expire after approximately one hour. Uploads and generated files are processed on the machine hosting the Space, so use private visibility if you want to limit access to the app. The service does not publish outputs to a dataset or send them to a separate inference API.

## Architecture and source

- `app.py`: Gradio interface; a separate, lightweight Python environment.
- `runner.py`: One GPU job at a time, worker timeouts/cancellation, temporary file cleanup.
- `worker.py`: Demucs separation, Seed-VC singing, Qwen3-TTS voice-clone speech.
- `audio_utils.py`: File validation, crossfades, dynamics, mix, mastering, export.
- `vendor/seed_vc/`: Required Seed-VC inference source, upstream licenses, and documented small patches. No model checkpoints are bundled.
- `assets/`: Default singing/speech references derived from the supplied archival recording. No source song is bundled.
- `models.json`: Pinned model revisions and source provenance.
- `tests/`: CPU regression checks; `VALIDATION.md` records integration testing and deployment limits.

Three Python environments avoid the incompatible Hugging Face Hub / Transformers requirements of the current UI, singing model, and speech model. The two model environments share PyTorch 2.7.1 CUDA 12.8 wheels. FlashAttention and GPU video encoding are not required. Video export uses FFmpeg's CPU H.264 encoder.

## Run with Docker

```sh
docker build -t wang-voice .
docker run --rm --gpus all -p 7860:7860 wang-voice
```

Open `http://localhost:7860`. Docker needs an NVIDIA-capable runtime for generation. Model weights download at runtime, never during the image build.

Optional runtime environment variables (also usable in Space Settings):

| Variable | Default | Purpose |
|---|---|---|
| `MAX_SONG_SECONDS` | `600` | Maximum song duration; full songs are processed in 40-second overlapping windows |
| `MAX_UPLOAD_MB` | `500` | Upload size limit |
| `MAX_TEXT_CHARS` | `600` | Speech text limit |
| `JOB_TIMEOUT_SECONDS` | `7200` | Maximum runtime per job, including initial downloads |
| `RESULT_TTL_SECONDS` | `3600` | Retention of job downloads |
| `MODEL_CACHE` | `/home/user/.cache/wang-voice` | Writable cache directory |
| `CPU_THREADS` | `4` | PyTorch CPU thread count |

The default filesystem cache disappears on a Space rebuild/restart if no persistent storage is configured. Only set `MODEL_CACHE` to persistent storage after mounting it using your hosting configuration. Never put cache directories or downloaded checkpoints in the Space's git repository.

For local source development, install `requirements-ui.txt` in a web venv. Install compatible CUDA PyTorch/torchaudio and `requirements-singing.txt` / `requirements-tts.txt` in two separate model venvs. Set `SING_PYTHON` and `TTS_PYTHON` to their Python executables, install FFmpeg and SoX, then run `python app.py` in the web venv. The Dockerfile is the canonical deployment recipe.

## Licenses and attribution

Project code is GPL-3.0; see `LICENSE`. Seed-VC source and checkpoint are GPL-3.0. Qwen3-TTS code and the 0.6B Base checkpoint are Apache-2.0. Demucs is MIT. Consult [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the linked upstream model cards for the other components.

The two archival WAV excerpts are user-supplied reference material and are **excluded from the software license**. The project does not claim ownership of, or grant new redistribution rights to, those recordings. Their derivation and source-file hash are recorded in `assets/reference.json`. The GPL metadata on this Space applies to software, not to those audio recordings or users' uploaded songs.

This app generates an AI interpretation and is not affiliated with or endorsed by the depicted person. Preserve the AI-generated label when sharing outputs.
