# API（v0.3.0）

本地 Gradio API `/generate` 参数顺序：text, upload, performance, quality, vocals, music, video, language。

- text / upload 只能填写一种。upload 用 gradio_client.handle_file(path)。
- performance: auto（默认）, low, balanced, fast。低空闲显存可自动降档。
- quality: 20, 40（默认）, 60；vocals: 4.5；music: -1.5；video: true；language: Chinese。
- 返回顺序：试听 MP3、下载 MP3、FLAC、WAV、MP4（可能为空）、生成 JSON、状态。

旧 `/sing` 保留 upload, vocal_db, music_db, quality, video 参数及原六项返回。
旧 `/speak` 保留 text, language 参数及原五项返回。API 与界面共用同一 GPU 队列。

Worker 可接收 performance 字段。生成 JSON 记录档位、总显存、空闲显存、PyTorch 分配/保留峰值及耗时。
诊断环境变量 VOICE_TEST_BUDGET_MIB 仅供受限测试，限制 PyTorch 分配器，不代表驱动总显存或物理小显存显卡。


## 持久化与新界面

旧 `/generate` 参数及返回顺序保留。新 `/create`、`/preview`、`/redo` 由界面调用，包含会话状态；程序集成建议继续使用 `/generate`。导出文件现在自动保存到持久作品目录；可修改素材按 7 天、约 5 GB 的预算清理，上传与参考原话仍只在本机私有目录处理。旧临时下载 URL 的缓存期限不等于本机作品文件的保存期限。
