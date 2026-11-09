# Windows quickstart — v0.3.1

[中文完整手册](Windows-Setup.zh-CN.md)

Download the Windows release ZIP, extract it completely, run Start Voice Studio.exe and click **安装并打开工作室** (Set up and open). Keep the launcher open.

Enter text OR upload a vocal audio/video file, then click **一键生成** (Generate). Download MP3 or lossless FLAC; WAV/video/parameters are under More downloads. Advanced settings are optional.

Requires 64-bit Windows 10/11, a 6 GB-class or larger NVIDIA GPU and driver, internet for first downloads, recommended 16 GB system RAM and 30 GB free setup disk space. Physical 6 GB hardware is still untested; allocator-limited tests on a 16 GB card are documented in [validation](v0.3.0-Validation.md).

Automatic profiles trade CPU work and model transfers for memory; they do not change default weights, precision, pitch or 40 steps. Close GPU applications and choose the 6 GB profile if out of memory. Re-run **修复安装** (Repair setup) for installation errors. **停止** means Stop; **打开安装日志** opens setup logs. App logs are in .runtime/app.log.

Successful installation removes only .runtime/pip-cache and .runtime/downloads. Models remain in .cache. Preserve .runtime and .cache to keep using the installation. There is no automatic upgrade: save outputs, close the launcher, download a new release to a new folder, optionally copy .cache, and install. Repair setup refreshes environment paths after moving an existing folder.

All audio is an AI interpretation, not an authentic recording. Software is GPL-3.0; archival recordings have separate rights notices.

## Desktop shortcut

First launcher run and successful setup create a current-user desktop shortcut. After setup, double-click it to start the local server and open the studio directly. A second click reuses the running instance. Keep the extracted app folder. After moving it, run the EXE from the new location or use 创建 / 修复桌面快捷方式 (Create / repair desktop shortcut). Downloading a ZIP alone does not execute the app. Desktop permission errors do not invalidate installation.
