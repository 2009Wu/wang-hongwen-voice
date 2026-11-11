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

## 安装体积 / Disk use

安装与启动时自动清理本程序不使用的 PyTorch 开发静态库和 ffplay 播放器，实测运行环境节省 980,103,826 字节（约 980 MB / 0.91 GiB）。不改模型权重、运行 DLL、精度、步数、音高和混音。保留模型缓存和 Python 缓存。安装时仍需预留 30 GB，首次仍会下载数 GB。

开发者需要编译自定义 C++ 扩展时，请另建完整开发环境；启动器维护的是配音和翻唱所需的推理环境。升级时先保存结果、关闭启动器，把新 ZIP 完整解压覆盖回原位置，可保留 `.runtime` 和 `.cache`；下次打开会自动精简。请勿只复制 EXE。


安装前的 30 GB 可用空间包含下载、解压临时文件，不是装好后长期占用。自选音色装好并缓存全部模型后实测约 11.25 GiB；王洪文主要模型和运行库接近，实际大小随缓存与结果变化。v0.3.3 进一步清理不使用的演示资源、开发头文件和工具文档，保留模型、音质参数和加速缓存。


新版：作品自动保存、作品历史、歌曲试听、局部重做、共用模型缓存和更新回退。详细步骤见 docs/作品与更新.md。
