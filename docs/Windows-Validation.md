# Windows release validation · v0.2.0

The Windows launcher was tested on Windows 11 x64 with an RTX 5070 Ti (16 GB-class VRAM) and NVIDIA driver 621.01. The setup used a fresh private Python distribution and newly installed environments, without the existing project's Python package overlays.

## Passed

- Downloaded CPython 3.12.10 and FFmpeg 8.1.2 from the pinned providers and checked both SHA-256 values.
- Installed CUDA PyTorch / torchaudio 2.7.1 and all three app environments from an empty `.runtime/` folder. This took approximately 375 seconds on the test PC and connection; other connections/PCs can take longer.
- Executed a real CUDA tensor operation and the UI, singing, speech, FFmpeg, and ffprobe installation checks.
- Launched the app through the compiled EXE and used its actual `/sing` and `/speak` APIs. Singing converted a 44-second MP4 across two outer chunks, returning stereo WAV, MP3, MP4, and metadata. Chinese speech returned WAV and MP3.
- The singing WAV contained 1,940,480 stereo samples at 44,100 Hz, exactly matching the input decoded by the bundled FFmpeg. Both audio outputs had finite samples without clipping; all exports decoded successfully. The speech WAV was approximately six seconds at 24,000 Hz.
- Nine CPU regression checks passed in the newly installed singing environment.
- The launcher self-test verified a real Windows process argument round-trip with spaces, Chinese text, quotes, trailing backslashes, and shell punctuation. Archive traversal paths were rejected.
- Moved the installed app to a folder with spaces and Chinese characters, ran setup repair successfully, and verified the installed GUI reported it ready.
- Visually checked the native Windows window, used **Open Voice Studio**, verified that the browser opened the local app, and used **Stop** to shut down the server.

## Limits

This validates the fresh app environment on one Windows machine. It does not cover a clean Windows OS image, every GPU/driver combination, or macOS/Linux. Windows systems can still require graphics driver or operating-system runtime updates. The launcher is not code-signed.

Model weights download during first generation and are not bundled in the small Windows ZIP. Docker deployment remains untested in this release environment. The original pipeline and separate Gradio package validation are described in the main [VALIDATION.md](../VALIDATION.md).
