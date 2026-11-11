# v0.4.0 — 作品历史与歌曲试听

## v0.4.1 · 启动时自动更新

- 打开 Windows 工作室时，启动器自动检查并安装已发布的新版。通过 SHA-256 和文件清单校验后才会替换程序文件，完成后自动打开工作室。
- 更新在网页打开前进行。网络异常或检查超时后会继续启动，成功检查后六小时内跳过重复检查。
- “更新与帮助”可以关闭自动更新，也可以手动更新和回退。回退后，自动更新会等到发布更高版本。
- 已安装旧版的用户，在“更新与帮助”手动更新一次，或从发布页下载新版安装包。作品、收藏音色和模型缓存继续沿用。

Windows now checks for and installs verified releases before opening the studio. Use Updates & Help to switch automatic updates off, update manually, or roll back. Install this release once from the existing updater to enable the feature.

- 生成后自动保存作品，关闭程序后可从历史载入、试听和下载。
- 歌曲支持 10 / 15 / 20 秒试听，再沿用确认片段生成整首。
- 可选择最多 120 秒区间单独重做，新旧作品分别保留。
- 两个工作室共用模型缓存，整理旧缓存时保留相同模型内容。
- 增加检查更新、下载校验、安装重启、回退和不含录音文字的诊断报告。

模型、参考素材、默认 40 步、音高、推理精度和混音默认值不变。物理 6 GB 显卡仍需更多实机验证，配置要求不变。

首次升级请下载下方完整 Windows ZIP，关闭启动器后覆盖原程序目录并保留 `.runtime`。不要只替换 EXE。以后的更新可在程序“更新与帮助”中完成。ZIP 不含模型权重，首次安装仍需联网下载数 GB。

作品保存在系统“文档”里的 Voice Studio作品。用于重做的素材保留 7 天、总量约 5 GB；最终作品不会自动删除。详细操作见 docs/作品与更新.md。

English: persistent works history, short cover previews with reuse, selected-interval redo, shared model cache, verified explicit updates and rollback. Custom edition also supports local voice favorites and reference trimming. Engines and default audio quality settings are unchanged.


# 版本更新 / Changelog

## v0.3.3 — 安装空间说明与进一步精简

- 明确 30 GB 是首次安装前的可用空间要求（含临时文件）；自选音色装好并缓存完整模型后实测约 11.25 GiB。
- 清理本程序不使用的上游演示界面、开发头文件和工具文档，当前环境再减少 183,939,829 字节，约 184 MB。
- 保留当前界面、许可文件、模型、运行 DLL、Python 与模型加速缓存；不改生成计算、精度、步数和导出设置。
- 完成后记录精简状态，下次启动不再扫描数千个文件；修复安装后自动重新清理。

English: Clarify temporary setup space versus installed size and trim unused demo assets, headers and tool manuals without changing the inference runtime or model settings.

## v0.3.2 — 精简安装体积

- 安装与启动时自动清理本程序不使用的 PyTorch 开发静态库和 ffplay 播放器，实测运行环境节省 980,103,826 字节（约 980 MB / 0.91 GiB）。不改模型权重、运行 DLL、精度、步数、音高和混音。保留模型缓存和 Python 缓存。安装时仍需预留 30 GB，首次仍会下载数 GB。
- Windows 包约 2.4 MB，参考录音无损打包，启动前还原为原始 WAV 并核对 SHA-256。
- 已验证两个程序的真实配音和翻唱；同一段自选配音在精简前后 WAV 逐字节一致。

English: Remove unused build-only files from the private inference runtime; preserve model weights, generation settings, runtime DLLs and caches.

[中文首页](README.md) · [English README](README.en.md) · [全部发布版本 / Releases](https://github.com/2009Wu/wang-hongwen-voice/releases)

## v0.3.1 — 桌面一键打开

- 使用用户提供的照片作为程序、启动器窗口与桌面快捷方式图标；包含多尺寸 ICO，保留完整原照片。

- 首次运行和安装成功后自动创建中文桌面快捷方式；安装后双击直接启动并打开网页。
- 重复点击复用已有启动器；新增「创建 / 修复桌面快捷方式」，支持移动目录后修复入口。
- 桌面写入失败不会导致安装失败；不改变生成模型、参考音频或音质参数。

English: Automatic per-user desktop shortcuts, direct opening after setup, single-instance reuse and shortcut repair after moving the app folder.

## v0.3.0 — 低显存与中文一键生成

- 6 GB 级显卡起步，自动按空闲显存选择节省/均衡/性能档位；低档 CPU 分离伴奏并分阶段载入 GPU。
- 中文启动器与统一首页，输入文字或放入文件即可一键生成；高级选项默认收起，保留旧 API。
- 保留模型、参考、默认 40 步和混音效果；新增与 WAV 样本完全一致的无损 FLAC。
- 发布 ZIP 改用无损压缩，成功安装自动清理安装下载缓存，保留模型与环境。
- 已进行 4.5 GiB 分配上限测试；物理 6 GB GPU 尚待验证，详见 docs/v0.3.0-Validation.md。

English: Automatic memory profiles, Chinese one-button workflow, lossless packaging/FLAC and setup-cache cleanup. Physical 6 GB hardware is not yet validated.

## [v0.2.2 — Windows 首次下载修复 / Windows first-download fix](https://github.com/2009Wu/wang-hongwen-voice/releases/tag/v0.2.2)

### 中文

- 修复普通 Windows 用户首次下载语音模型时可能出现的 `WinError 1314` 权限错误。
- Windows 上改为串行下载语音模型文件，避免上游缓存首次探测的并发问题；不要求管理员权限或更改 Windows 安全设置。
- 明确当前 Windows 启动器仍要求 16 GB 级显卡；8 GB 支持尚未验证。
- 补充公开 ZIP 全新安装和首次模型下载的验证记录。

验证：从公开 Hugging Face 下载入口取得 v0.2.1 ZIP，在空目录中自动安装独立运行环境，耗时约 364 秒。完整 222 秒歌曲的 WAV/MP3/MP4 转换通过。发现首次语音模型下载错误后应用本修复，移走失败缓存，重新从空语音模型目录下载并生成中文语音，WAV/MP3 解码通过。没有复用旧应用的 Python 或模型缓存。测试仍限于本机 Windows 11 / RTX 5070 Ti，不代表所有 Windows 配置或 8 GB 显卡均已验证。

### English

Fixed a first-use Windows speech-model download permission error by serializing snapshot downloads on Windows. No administrator rights or security-setting changes are required. A publicly downloaded v0.2.1 ZIP installed into an empty directory in about 364 seconds; its complete 222-second song conversion passed. After reproducing the speech download failure, this fix passed a fresh speech-model download and Chinese WAV/MP3 generation using that new private runtime. The launcher still requires a 16 GB-class NVIDIA GPU; 8 GB is unvalidated. See the Windows validation record for scope.

## [v0.2.1 — 中文新手说明包 / Chinese beginner documentation](https://github.com/2009Wu/wang-hongwen-voice/releases/tag/v0.2.1)

### 中文

- Windows ZIP 内加入《开始使用.txt》、完整中文安装与使用手册、英文按钮对照及版本更新日志。
- `START HERE.txt` 改为中文在前、英文在后，保留独立英文 README。
- GitHub 简介改为中文优先，并补充翻唱、语音与 Windows 相关主题标签。
- 新增发布附件打包流程：生成 Windows ZIP 和 SHA-256 校验文件，并上传到对应 Release。

本版只更新文档与打包流程，启动器、生成代码、模型配置和参考素材均沿用 v0.2.0。原 v0.2.0 发布包仍可下载。此版本完成了包完整性、中文文档、相对链接和运行文件一致性检查；未重复下载模型或宣称新增其他电脑的安装验证。

### English

The Windows package now includes a Chinese-first quickstart, complete Chinese installation/use guide, button translations, and changelog. English documentation remains available. Repository metadata is Chinese-first with relevant topics. A release workflow builds and uploads the Windows ZIP and checksum. Application code, launcher, model configuration, and reference assets are unchanged from v0.2.0; this is a documentation/package update. Package integrity and unchanged runtime files were checked without repeating model downloads or claiming new hardware validation.

## 早期在线文档更新 / Earlier online documentation update

### 中文

- 项目首页改为中文优先，英文说明移至 `README.en.md`。
- 新增完整的中文安装、使用、按钮对照、故障处理和升级说明。
- 新增中文快速开始文本和本版本更新记录。
- 发布说明及 Hugging Face 介绍同步采用中文在前、英文在后的顺序。

本次为在线文档更新；v0.2.0 已发布 Windows ZIP 的内容与校验值保持原样。最新中文说明以本仓库网页为准。

### English

- Made Chinese the default README and kept a separate English README.
- Added a complete Chinese Windows installation, usage, troubleshooting, and update guide.
- Added a Chinese quickstart and this changelog.
- Updated public descriptions and release notes to put Chinese first.

This documentation update leaves the published v0.2.0 Windows ZIP and checksum unchanged. Use the repository's online pages for the latest Chinese instructions.

## [v0.2.0 — Windows 安装向导 / Windows setup wizard](https://github.com/2009Wu/wang-hongwen-voice/releases/tag/v0.2.0)

### 新增

- 可双击启动的 Windows 图形化安装器与启动器。
- 自动检测 NVIDIA 显卡和磁盘空间。
- 自动准备独立 Python、CUDA PyTorch、FFmpeg 和三套应用环境。
- Python 与 FFmpeg 下载采用固定地址和 SHA-256 校验。
- 安装进度、详细日志、修复安装、自动打开浏览器及停止按钮。
- Windows 新手说明和安装验证记录。

### 验证

完成全新应用环境安装、跨分段歌曲翻唱、MP4 导出、中文文字语音生成、九项回归检查、窗口打开/停止，以及含空格和中文路径的移动修复测试。测试平台为 Windows 11 / RTX 5070 Ti；不代表所有 Windows 或所有显卡均已验证。

### English

Added a native Windows setup/launcher with hardware checks, automatic private dependencies, verified runtime downloads, repair, progress/logs, browser launch, and Stop controls. Fresh-install singing and Chinese speech integration, nine regression checks, and moved-path repair were tested on Windows 11 with an RTX 5070 Ti.

## 首次开源发布 / Initial source publication

首次公开了歌曲翻唱、文字转语音、参考音频、Gradio 界面、Docker 配置和相关测试/许可文档。该次发布没有独立的版本标签。

The initial source publication included singing conversion, speech generation, references, the Gradio interface, Docker configuration, tests, and license notices. It had no separate release tag.
