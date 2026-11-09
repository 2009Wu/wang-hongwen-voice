"""Wang Hongwen Voice Studio · Hugging Face Docker Space."""
import os
from pathlib import Path

import gradio as gr

from runner import run_job
from settings import ASSETS, CACHE, LANGUAGES, MAX_MB, MAX_SECONDS, MAX_TEXT, ROOT

CSS = """
.gradio-container { max-width: 1180px !important; margin: auto; }
#masthead { padding: 30px 2px 22px; }
#masthead .eyebrow { color: #a43c32; font-size: 12px; font-weight: 700; letter-spacing: .16em; }
#masthead h1 { font-size: clamp(30px, 5vw, 47px); letter-spacing: -.045em; margin: 8px 0 10px; line-height: 1.12; }
#masthead p { font-size: 16px; color: #68717c; max-width: 710px; line-height: 1.6; margin: 0; }
#masthead .zh { font-weight: 400; font-size: .55em; color: #a43c32; margin-left: 12px; letter-spacing: .04em; white-space: nowrap; }
.note { font-size: 13px; color: #68717c; }
.panel-title { margin-top: 6px !important; }
footer { display: none !important; }
"""


def singing(upload, vocal_db, music_db, quality, video, progress=gr.Progress()):
    if not upload:
        raise gr.Error("Upload the song you want him to sing.")
    path = Path(upload)
    if not path.is_file() or path.stat().st_size > MAX_MB * 1024**2:
        raise gr.Error(f"Choose an audio/video file under {MAX_MB} MB.")
    request = {"mode": "sing", "input": str(path.resolve()), "vocal_db": vocal_db,
               "music_db": music_db, "steps": quality, "video": video}
    yield None, None, None, None, None, "Starting…"
    try:
        for fraction, message, result in run_job(request):
            progress(fraction, desc=message)
            if result:
                yield result["audio"], result["wav"], result["audio"], result["video"], result["details"], message
            else:
                yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), message
    except Exception as error:
        raise gr.Error(str(error)) from error


def speech(text, language, progress=gr.Progress()):
    if not text.strip() or len(text.strip()) > MAX_TEXT:
        raise gr.Error(f"Enter 1–{MAX_TEXT} characters.")
    yield None, None, None, None, "Starting…"
    try:
        for fraction, message, result in run_job({"mode": "speak", "text": text.strip(), "language": language}):
            progress(fraction, desc=message)
            if result:
                yield result["audio"], result["wav"], result["audio"], result["details"], message
            else:
                yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), message
    except Exception as error:
        raise gr.Error(str(error)) from error


def make_request(text, upload, performance="auto", quality=40, vocals=4.5, music=-1.5, video=True, language="Chinese"):
    text = (text or "").strip()
    if bool(text) == bool(upload):
        raise ValueError("请输入文字或放入一个音频/视频文件；一次只选一种。")
    if text:
        if len(text) > MAX_TEXT:
            raise ValueError(f"文字最多 {MAX_TEXT} 字。")
        return {"mode": "speak", "text": text, "language": language, "performance": performance}
    path = Path(upload)
    if not path.is_file() or path.stat().st_size > MAX_MB * 1024**2:
        raise ValueError(f"请选择不超过 {MAX_MB} MB 的音频/视频。")
    return {"mode": "sing", "input": str(path.resolve()), "performance": performance,
            "steps": quality, "vocal_db": vocals, "music_db": music, "video": video}


def generate(text, upload, performance, quality, vocals, music, video, language, progress=gr.Progress()):
    try:
        request = make_request(text, upload, performance, quality, vocals, music, video, language)
        yield None, None, None, None, None, None, "准备生成…"
        for fraction, message, result in run_job(request):
            progress(fraction, desc=message)
            if result:
                yield result["audio"], result["audio"], result.get("flac"), result["wav"], result["video"], result["details"], message
            else:
                yield *(gr.skip() for _ in range(6)), message
    except Exception as error:
        raise gr.Error(str(error)) from error


def build_app():
    with gr.Blocks(title="王洪文语音工作室", delete_cache=(600, 3600)) as demo:
        gr.Markdown("# 王洪文语音工作室\n输入文字，或放入有原唱的音频/视频，然后点击 **一键生成**。")
        gr.Markdown("首次生成会下载模型；以后会使用本地缓存。使用期间请保持启动器开启。", elem_classes="note")
        with gr.Row(equal_height=False):
            with gr.Column(scale=6):
                text = gr.Textbox(label="文字 → 生成语音", placeholder="输入你想让他说的话……", lines=4)
                upload = gr.File(label="音频/视频 → 生成翻唱", type="filepath",
                                 file_types=[".mp3", ".wav", ".m4a", ".mp4", ".flac", ".ogg", ".webm", ".mov", ".aac", ".mkv"])
                gr.Markdown(f"两种输入任选其一。文字最多 {MAX_TEXT} 字；文件最多 {MAX_MB} MB、{MAX_SECONDS // 60} 分钟。", elem_classes="note")
                with gr.Accordion("高级选项（通常无需修改）", open=False):
                    performance = gr.Dropdown(choices=[("自动选择（推荐）", "auto"), ("6 GB 节省显存 · 较慢", "low"),
                                                       ("8 GB 均衡", "balanced"), ("12 GB+ 性能优先", "fast")], value="auto", label="性能档位")
                    gr.Markdown("自动根据可用显存选择；6 GB 模式用 CPU 分离伴奏并分阶段载入 GPU。显卡算力、CPU 和音频长度也会影响速度。")
                    quality = gr.Dropdown(choices=[("快速 · 20 步", 20), ("标准 · 40 步（默认）", 40), ("精细 · 60 步", 60)], value=40, label="翻唱质量")
                    vocals = gr.Slider(-2, 9, value=4.5, step=.5, label="人声响度（dB）")
                    music = gr.Slider(-12, 3, value=-1.5, step=.5, label="伴奏响度（dB）")
                    video = gr.Checkbox(True, label="输入为视频时，同时导出 MP4")
                    language = gr.Dropdown(LANGUAGES, value="Chinese", label="文字朗读语言（中文最贴近参考声音）")
                with gr.Row():
                    create = gr.Button("一键生成", variant="primary", scale=3)
                    stop = gr.Button("停止", scale=1)
            with gr.Column(scale=5):
                status = gr.Textbox(label="进度", value="等待文字或文件。", interactive=False)
                audio = gr.Audio(label="AI 生成试听", type="filepath", interactive=False)
                mp3 = gr.DownloadButton("下载 MP3 · 通用")
                flac = gr.DownloadButton("下载 FLAC · 无损且更小")
                with gr.Accordion("更多下载", open=False):
                    wav = gr.DownloadButton("下载 WAV · 无损")
                    movie = gr.DownloadButton("下载 MP4 · 翻唱视频")
                    details = gr.DownloadButton("下载生成参数和显存记录")
        gr.Markdown("**所有输出均为 AI 合成演绎，并非王洪文真实录音。** 相似度取决于素材。结果临时保留，请及时下载保存。", elem_classes="note")
        event = create.click(generate, [text, upload, performance, quality, vocals, music, video, language],
                             [audio, mp3, flac, wav, movie, details, status], api_name="generate",
                             concurrency_limit=1, concurrency_id="gpu")
        stop.click(lambda: "已停止，可以重新生成。", outputs=status, cancels=[event], queue=False, api_name=False)
        # Keep the v0.2 sing/speak API contracts for existing scripts.
        with gr.Column(visible=False):
            legacy_song = gr.Button("legacy sing")
            legacy_speech = gr.Button("legacy speak")
            legacy_song_status = gr.Textbox()
            legacy_speech_status = gr.Textbox()
        legacy_song.click(singing, [upload, vocals, music, quality, video], [audio, wav, mp3, movie, details, legacy_song_status],
                          api_name="sing", concurrency_limit=1, concurrency_id="gpu")
        legacy_speech.click(speech, [text, language], [audio, wav, mp3, details, legacy_speech_status],
                            api_name="speak", concurrency_limit=1, concurrency_id="gpu")
    return demo


if __name__ == "__main__":
    demo = build_app()
    demo.queue(max_size=8, default_concurrency_limit=1).launch(
        server_name=os.getenv("HOST", "0.0.0.0"), server_port=int(os.getenv("PORT", "7860")),
        theme=gr.themes.Soft(primary_hue="red", neutral_hue="slate", font=["Inter", "system-ui", "sans-serif"]), css=CSS,
        max_file_size=f"{MAX_MB}mb", show_error=False,
        blocked_paths=[str(ASSETS), str(CACHE), str(ROOT / "vendor"), str(ROOT / ".runtime")],
        footer_links=[],
    )
