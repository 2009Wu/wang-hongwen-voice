# Windows 下载验证与首次下载修复 · v0.2.2

## 本次验证（中文）

- 从 Hugging Face 公开页面的按钮重新下载 GitHub v0.2.1 Windows ZIP，核对附件 SHA-256。
- 解压到一个全新目录，确认没有 `.runtime` 或模型缓存；安装器自动准备独立 Python、FFmpeg 和三个环境，约 363.7 秒后通过 GPU/组件检查。
- 实际转换完整 222.42 秒的原歌曲视频，使用默认 40 步、人声 +4.5 dB、伴奏 −1.5 dB，处理六个分段，生成 WAV、MP3 和 MP4；三种导出均完整解码，长度一致。
- 首次语音模型下载复现了 `WinError 1314`。定位为上游缓存符号链接支持探测的并发问题；[上游问题 #4915](https://github.com/huggingface/huggingface_hub/issues/4915) 记录了相同原因和串行下载的处理方式。
- 本版在 Windows 上将该次快照下载设置为单线程。移走失败缓存后，在空语音模型目录中重新下载并实际生成中文语音，约 6.72 秒的 WAV、MP3 均成功解码。
- 原有应用的 Python、模型文件及源码没有复制到新安装中。首次模型下载没有使用账号令牌；管理员权限和 Windows 安全设置没有改变。

## 范围与限制

本次验证的是现有 Windows 11 / RTX 5070 Ti（16 GB 级）电脑上的全新应用环境，不是重装 Windows 的空白系统。v0.2.1 的完整歌曲转换先通过；v0.2.2 针对同一新环境验证了修复后的首次语音下载。当前启动器仍检查 16 GB 级显存，8 GB 运行尚未验证。启动器未签名，其他硬件仍可能需要检查。公开 v0.2.2 附件另行核对校验值和修复代码。

## English

The public v0.2.1 ZIP was downloaded through the Hugging Face page, checksum-verified, and installed into an empty app directory without copying another installation's Python or model cache. Setup took 363.7 seconds. A complete 222-second vocal song/video passed WAV, MP3 and MP4 export and decoding. The first speech-model download reproduced a Windows symlink-probe race. Serializing that download on Windows passed a new empty speech-model cache download and Chinese speech generation (6.72-second WAV/MP3). No administrator elevation or Windows security change was used. This is one Windows 11 / RTX 5070 Ti machine, not a clean OS image or an 8 GB GPU validation.

---

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
