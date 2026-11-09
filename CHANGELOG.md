# 版本更新 / Changelog

[中文首页](README.md) · [English README](README.en.md) · [全部发布版本 / Releases](https://github.com/2009Wu/wang-hongwen-voice/releases)

## 在线文档更新 / Online documentation update

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
