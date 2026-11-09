# Windows setup for beginners

[Fresh-install and launcher validation](Windows-Validation.md).

Use the **Windows ZIP** from [GitHub Releases](https://github.com/2009Wu/wang-hongwen-voice/releases/latest). Extract the whole archive to a permanent folder, then double-click **Start Voice Studio.exe**.

Click **Set up & open Voice Studio**. The launcher checks the PC, downloads and verifies a private Python runtime and FFmpeg, installs the required GPU libraries, and prepares three isolated environments. When setup is complete, the local app opens in your browser. No terminal, Docker, Python installation, or service account is required.

On later launches, click **Open Voice Studio**. Leave the launcher open while using the app; **Stop** or closing the launcher shuts down its local server and GPU workers. Your generated downloads remain temporary, so save them.

## What the PC needs

- 64-bit Windows 10 or 11, with the .NET Framework normally provided by Windows.
- A 16 GB-class or larger NVIDIA CUDA GPU and a current NVIDIA driver. This release checks for at least approximately 14.2 GiB of reported video memory to include 16 GB-class cards with reserved memory.
- At least 30 GB free space on the drive containing the extracted folder.
- Internet for setup and the first singing/speech generations. Both stages download several GB. The small release ZIP does not contain the model weights.

This launcher is for Windows/NVIDIA users. Other configurations can use the documented Python/Docker setup where supported. Hardware requirements still apply to the downloaded app; the public Hugging Face page hosts the source and sample.

## Where files go

The private Python distribution, Python environments, downloaded installers, pip cache, and setup/app logs are kept in **`.runtime/`** beside the app. Model weights are kept in **`.cache/`**. These folders are excluded from git and Docker builds. The launcher uses process-local environment settings and does not change the system Python, registry, PATH, or graphics driver.

The local web app listens on **127.0.0.1**. It chooses an available port near 7860 and opens the resulting address automatically. Closing the browser tab alone leaves the launcher and server running.

If you move the folder after setup, the launcher detects the changed location; use **Repair setup** to refresh its environment paths.

## When something needs attention

| What you see | What to do |
|---|---|
| NVIDIA card or driver not detected | Install/update the driver from NVIDIA, restart Windows, and retry |
| Not enough GPU memory | Use a supported 16 GB+ NVIDIA card |
| Less than 30 GB free | Free space on the app's drive, then retry |
| Download interrupted | Reopen the launcher and use **Repair setup**; completed downloads are reused |
| Checksum mismatch | Retry setup; a mismatched archive is never executed |
| Setup or interface failed | Use **Open setup log**; `.runtime/app.log` contains interface/worker errors |
| Windows path-length error during package install | Extract the app to a short path such as `C:\VoiceStudio`, then retry setup there |

The EXE is not code-signed. Its source and build instructions are included in this repository. The runtime downloads are pinned and checksum-verified, and Python packages come from PyPI / the official PyTorch wheel index. Do not change Windows security settings to install the app.

## Source, rebuild, and checks

The GUI launcher source is [windows/VoiceStudioLauncher.cs](../windows/VoiceStudioLauncher.cs). Developers can run [windows/Build-Launcher.ps1](../windows/Build-Launcher.ps1) with the .NET Framework C# compiler to rebuild it. The [runtime-pins.json](../windows/runtime-pins.json) file records the Python and FFmpeg download URLs and SHA-256 checksums. Build outputs can vary between compiler invocations; the published release checksum identifies that specific ZIP.

Python uses the CPython team's [NuGet distribution](https://docs.python.org/3.12/using/windows.html#the-nuget-org-packages). FFmpeg comes from [Gyan's Windows builds](https://www.gyan.dev/ffmpeg/builds/), linked by the [FFmpeg project](https://ffmpeg.org/download.html). Downloaded distributions retain their license/source information. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

For scripted validation, the EXE supports `--self-test`, `--diagnose`, `--install-only`, and `--serve-only`, with optional `--root` for an extracted app directory. `--serve-only` can take `--port`. These flags are for development; beginners can use the normal window.
