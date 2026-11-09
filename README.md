# 王洪文语音工作室 · Wang Hongwen Voice Studio

**简体中文** · [English](README.en.md) · [中文手册](docs/Windows-Setup.zh-CN.md) · [版本更新](CHANGELOG.md)

开源 AI 歌曲翻唱和文字语音工具。**输入文字，或放入有原唱的音频/视频，点击「一键生成」。** 自动识别任务，无需选择模型。

**[下载 Windows 版](https://github.com/2009Wu/wang-hongwen-voice/releases/latest/download/Wang-Hongwen-Voice-Studio-Windows.zip)** · [全部版本](https://github.com/2009Wu/wang-hongwen-voice/releases) · [Hugging Face 项目和试听](https://huggingface.co/spaces/Little-Wang/wang-hongwen-voice)

## 桌面一键打开

完整解压后首次运行启动器，会自动在当前用户桌面创建「王洪文语音工作室」快捷方式；安装成功后也会补建。以后双击桌面图标，程序自动启动本地服务并打开网页，无需再次点击「打开工作室」。重复点击会打开已有实例。首次使用仍需完成安装，单纯下载 ZIP 不会自动执行程序。

请保留完整程序文件夹。移动程序后，运行新位置的 EXE，或在启动器底部点击「创建 / 修复桌面快捷方式」。桌面权限受限时，快捷方式失败不会阻止安装；仍可运行 EXE。使用期间保持启动器开启。

## 三步开始

1. 下载 **Wang-Hongwen-Voice-Studio-Windows.zip**，完整解压。
2. 双击 **Start Voice Studio.exe**，点击 **安装并打开工作室**。
3. 浏览器打开后，输入文字或放入歌曲，点击 **一键生成**，完成后试听、下载。

无需手动安装 Python、Docker 或输入命令。以后点击 **打开工作室**。使用期间保持启动器开启。

## 配置要求与自动档位

64 位 Windows 10/11、**6 GB 级或以上 NVIDIA 显卡**及可用驱动，建议 16 GB 以上系统内存、安装前预留 30 GB 磁盘空间。首次安装和首次生成需联网下载数 GB；之后使用本地模型缓存。

| 可用显存档位 | 自动处理方式 |
|---|---|
| 6 GB 起步 | CPU 分离伴奏，扩散模型与声码器分阶段使用 GPU，速度较慢 |
| 8 GB 均衡 | GPU 分离伴奏，生成阶段节省显存 |
| 12 GB+ 性能优先 | 更多模型常驻 GPU，减少搬运等待 |

默认 **自动选择**，根据当前可用显存降低档位。高级选项可手动选择节省显存模式。显卡算力、CPU、驱动和输入长度也影响速度；显存更大本身不保证固定倍数加速。

**验证范围：** 已在 Windows 11 / RTX 5070 Ti 16 GB 上，用 **4.5 GiB PyTorch 分配上限**验证低显存翻唱和中文语音。物理 6 GB 显卡尚待实机验证，不能保证所有型号及占用状态都能运行。详见 [v0.3.0 验证](docs/v0.3.0-Validation.md)。

![中文一键生成界面](docs/app-preview.png)

## 默认效果和文件体积

- 保留原模型、参考音频、旋律和音高；默认 **40 步**、主唱 **+4.5 dB**、伴奏 **−1.5 dB**、原人声清晰度处理。
- 下载 **MP3 320 kbps**，或 **FLAC 无损音频**。FLAC 与 WAV 解码后的 24 位 PCM 样本完全一致，通常更小；WAV 也保留。
- 输入视频可同时导出 MP4。默认文件限制 500 MB、10 分钟，文字最多 600 字。
- 安装包采用无损 ZIP 压缩；模型权重不量化、不裁剪。安装成功后自动清理 pip 下载缓存与安装压缩包，保留模型和运行环境。

文字和文件一次任选一种，两者都填会提示处理，避免误生成。高级选项默认收起，通常无需修改。首次下载较慢，请观察中文进度；生成结果临时保留，请及时保存。

## 更新、开发和部署

当前版本 **[v0.3.1：桌面一键打开与照片图标](https://github.com/2009Wu/wang-hongwen-voice/releases/tag/v0.3.1)**。

程序没有自动升级；「修复安装」只修复环境。升级前保存结果并关闭启动器，下载新 ZIP 完整解压。可复制旧目录 `.cache` 复用模型；环境移动后使用修复安装。完整方法见[中文手册](docs/Windows-Setup.zh-CN.md)。

开发者见 [English README](README.en.md)、[Dockerfile](Dockerfile) 和 [API](docs/API.md)。新接口 `/generate` 自动选择任务，保留旧 `/sing`、`/speak` 接口。Docker 镜像未在此次环境构建验证。

Hugging Face 是免费项目介绍、试听和下载入口；生成在下载程序的电脑上完成，当前没有免安装的在线 GPU 服务。输入歌曲和文字不会自动公开或提交给外部推理 API。

## 许可和合成说明

软件采用 [GPL-3.0](LICENSE)。上游模型及许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [models.json](models.json)。历史讲话参考素材不属于软件 GPL 授权范围，来源和权利说明见 [assets/reference.json](assets/reference.json)。

使用参考音频条件生成，没有单独训练的「王洪文专用权重」。相似度受歌曲、文字及历史录音质量影响；纯伴奏不会自动生成歌词和演唱。

**所有输出均为 AI 合成演绎，并非王洪文真实录音或演唱。分享时请保留 AI 标注。**
