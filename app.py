"""Wang Hongwen Voice Studio · Hugging Face Docker Space."""
import os
from pathlib import Path

import gradio as gr
from studio_paths import public_output_paths

from runner import run_job
from settings import ASSETS, CACHE, LANGUAGES, MAX_MB, MAX_SECONDS, MAX_TEXT, ROOT



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
    from studio_ui import build_app as build_shared
    return build_shared(globals())


if __name__ == "__main__":
    from studio_presentation import launch_presentation, studio_theme
    demo = build_app()
    demo.queue(max_size=8, default_concurrency_limit=1).launch(
        server_name=os.getenv("HOST", "0.0.0.0"), server_port=int(os.getenv("PORT", "7860")),
        theme=studio_theme(),  **launch_presentation(),
        max_file_size=f"{MAX_MB}mb", show_error=False,allowed_paths=public_output_paths(),
        blocked_paths=[str(ASSETS), str(CACHE), str(ROOT / "vendor"), str(ROOT / ".runtime")],
        footer_links=[],
    )
