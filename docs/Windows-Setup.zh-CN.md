# Windows 中文安装与使用说明

[返回项目首页](../README.md) · [English instructions](Windows-Setup.md) · [版本更新](../CHANGELOG.md)

## 1. 安装前先看电脑配置

- 系统：64 位 Windows 10 或 Windows 11。
- 显卡：16 GB 级或更大显存的 NVIDIA 显卡，并安装可用的 NVIDIA 驱动。
- 空间：应用所在磁盘至少有 30 GB 剩余空间。
- 网络：首次安装和首次生成需要下载数 GB 文件。

启动器会检查配置。这个 Windows 版本面向 NVIDIA 显卡，不会把其他显卡变成 CUDA 显卡。当前应用环境只在一台 Windows 11 / RTX 5070 Ti 电脑上做过完整验证，详见 [Windows-Validation.md](Windows-Validation.md)。

## 2. 下载并安装

1. 打开 [GitHub 最新版本](https://github.com/2009Wu/wang-hongwen-voice/releases/latest)。
2. 在 **Assets** 中下载 **Wang-Hongwen-Voice-Studio-Windows.zip**。旁边的 `.sha256` 是用于校验下载完整性的文本文件，无需运行。
3. 将整个 ZIP 解压到准备长期保留的文件夹。请先解压，再运行程序。
4. 双击 **Start Voice Studio.exe**。
5. 点击 **Set up & open Voice Studio**（安装并打开工作室）。等待安装进度完成。
6. 浏览器自动打开本地工作室，接下来就可以生成音频。

第一次安装可能需要较长时间，速度取决于网络、磁盘和电脑。启动器会自动下载并检查 Python、FFmpeg，安装 GPU 库和应用环境；无需手动输入命令，也无需登录服务账号。

以后使用：再次打开同一个启动器，点击 **Open Voice Studio**。使用时保留启动器窗口；关闭浏览器标签页并不会自动关闭后台服务。

## 3. 英文按钮中文对照

| 界面文字 | 中文含义 |
|---|---|
| Set up & open Voice Studio | 首次安装并打开工作室 |
| Open Voice Studio | 打开工作室 |
| Repair setup | 修复、继续安装，或刷新移动后的路径 |
| Show setup details | 查看详细安装日志 |
| Open setup log | 打开安装日志 |
| Sing a song | 歌曲翻唱 |
| Text to speech | 文字转语音 |
| Create AI cover | 生成 AI 翻唱 |
| Generate speech | 生成语音 |
| Lead vocal level | 主唱音量 |
| Instrumental level | 伴奏音量 |
| Download WAV / MP3 / MP4 | 下载对应格式的结果 |
| Stop（网页内） | 停止当前生成任务 |
| Stop（启动器内） | 停止本地服务及其任务 |

## 4. 歌曲翻唱

1. 选择 **Sing a song**。
2. 上传含人声的歌曲或音乐视频，例如 MP3、WAV、M4A、MP4。
3. 新手可保留默认设置：主唱 +4.5 dB、伴奏 −1.5 dB、Standard 质量。
4. 点击 **Create AI cover**，等待状态栏显示完成。
5. 试听并点击下载按钮保存 WAV、MP3；视频输入勾选导出视频时还会提供 MP4。

默认最长 10 分钟、最大 500 MB。输入纯伴奏不会自动生成歌词或唱腔。伴奏分离不一定完美，部分原唱可能残留。

## 5. 文字转语音

1. 选择 **Text to speech**。
2. 输入要朗读的文字，默认最多 600 字符。
3. 中文内容选择 **Chinese**。
4. 点击 **Generate speech**，完成后试听并下载 WAV 或 MP3。

第一次使用每种功能会下载其模型，耗时比后续运行更长。歌曲翻唱和语音任务按顺序共用 GPU。生成结果是临时文件，请及时下载保存。

## 6. 文件放在哪里

应用文件夹中的 **`.runtime`** 保存独立 Python、应用环境、依赖缓存和日志；**`.cache`** 保存模型文件。启动器不会修改系统 Python、系统 PATH、注册表或显卡驱动。

本地页面只监听 **127.0.0.1**，会自动寻找可用端口并打开浏览器。用户音频和文字由运行应用的这台电脑处理，不会自动发布到 GitHub 或 Hugging Face。

## 7. 更新到新版本

目前没有自动更新功能，**Repair setup 也不等于升级应用版本**。

1. 下载并保存所有要保留的生成结果。
2. 点击启动器的 **Stop**，关闭启动器。
3. 到 [Releases](https://github.com/2009Wu/wang-hongwen-voice/releases) 查看新版本和发布说明，下载新的 Windows ZIP。
4. 建议解压到一个新文件夹，保留旧版本，方便出现问题时回退。
5. 如需复用已下载的模型，可在应用关闭后，将旧文件夹的 **`.cache`** 复制到新文件夹；无需复制 `.runtime`。
6. 打开新文件夹的启动器并完成安装。确认新版本正常后，再自行处理旧版本文件夹。

如果只是移动现有应用文件夹，在新位置运行 **Repair setup**，刷新 Python 环境路径即可。

## 8. 常见问题

| 情况 | 处理方法 |
|---|---|
| 没检测到 NVIDIA 显卡或驱动 | 检查显卡和 NVIDIA 驱动，必要时更新驱动、重启再试 |
| 显存不足 | 使用符合要求的 16 GB 级或更大显存 NVIDIA 显卡 |
| 磁盘空间不足 | 在应用所在磁盘腾出至少 30 GB 空间 |
| 下载中断 | 重新打开启动器，点击 Repair setup，已完成的下载可复用 |
| 下载校验失败 | 重新尝试安装；校验不符的压缩包不会被执行 |
| 安装失败或页面没打开 | 使用 Open setup log；界面或生成问题还可查看 `.runtime/app.log` |
| 文件路径过长 | 可尝试解压到较短路径，如 `C:\VoiceStudio`，再运行安装 |
| 第一次生成很慢 | 查看状态提示，模型可能仍在下载或加载 |

启动器目前没有代码签名。源代码及重建方式位于 `windows/`；不要为了安装而关闭 Windows 安全保护。

## 9. 许可与合成标注

软件为 GPL-3.0；历史录音参考素材不包含在软件许可内。所有生成语音和演唱均为 AI 合成演绎，并非真实历史录音或真实演唱。分享时请保留 AI 标注。
