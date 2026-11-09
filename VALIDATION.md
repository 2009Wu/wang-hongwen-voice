# Validation record

Latest: [v0.3.0 low-memory and one-button validation](docs/v0.3.0-Validation.md). Earlier results below are historical.

For the v0.2.0 Windows setup wizard and its fresh-install integration checks, see [docs/Windows-Validation.md](docs/Windows-Validation.md). The original app/package validation follows below.

Validated locally on Windows with Python 3.12.10, PyTorch 2.7.1 + CUDA 12.8, and an NVIDIA RTX 5070 Ti (16 GB VRAM).

## Executed checks

- Eight CPU regression tests passed: chunk reconstruction/tail coverage, stereo mix and centered lead, silence gating, lossless text chunking, media validation/mastering, scoped retention cleanup, real worker-process termination, and actionable errors.
- Actual public Gradio `/sing` API: uploaded a 44-second MP4, separated its stems, ran the default 40-step Seed-VC model across two overlapping windows, mixed/mastered the result, and downloaded WAV, MP3, MP4, and metadata through the app.
- Singing WAV: exactly 1,940,400 stereo samples at 44,100 Hz (44.000 seconds), finite samples and no clipping. MP3 and H.264/AAC MP4 decoded successfully; MP4 duration 44.000 seconds.
- Actual public Gradio `/speak` API: Chinese text produced a 24,000 Hz mono WAV and 320 kbps MP3; downloads and decoding succeeded. The welcome sentence produced approximately six seconds of speech. The new TTS voice has not received a separate listening approval from the user.
- Browser testing in headless Chromium: desktop 1440 px and mobile 390 px layouts, both tabs, text entry, no browser exceptions, no horizontal mobile overflow.
- The visible Stop button was tested during a real speech generation. The worker exited and private job files were cleaned in approximately 2.8 seconds after Stop. The regression suite also checks direct process termination.
- An empty text submission was rejected with the configured character-limit message.
- Linux x86_64 / Python 3.12 wheel availability and dependency resolution were checked for the pinned singing requirements. The dry run succeeded; this is not an actual Linux container build.
- With CUDA deliberately hidden, the worker exited promptly with the intended GPU-hardware setup message, before loading model weights.

## Scope and limits

The original singing pipeline also rendered the user's full 222.42-second song and received their approval. The newly packaged app was integration-tested on a 44-second excerpt, including a chunk boundary; its complete-song loop supports the configured ten-minute default limit.

Docker was unavailable in the local environment. The Docker image has **not** been built or run here, and the app has **not** been deployed on Hugging Face. The Dockerfile, SDK metadata, port, user permissions, dependency separation, and model download paths were prepared against the official Docker Spaces documentation. Cloud build/hardware differences remain to be verified after upload. Only Chinese TTS was integration-tested; the other exposed languages follow Qwen's published support list.

No source song, local virtual environment, downloaded checkpoint, authentication token, or user-specific absolute path is included in the upload package. Reference WAV files are intentionally included as the app's default voice and have a separate rights statement in the README.
