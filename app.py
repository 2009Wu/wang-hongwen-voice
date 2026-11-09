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


def build_app():
    with gr.Blocks(title="Wang Hongwen Voice Studio", delete_cache=(600, 3600)) as demo:
        gr.HTML('''<div id="masthead"><div class="eyebrow">VOICE STUDIO · AI INTERPRETATION</div>
        <h1>Wang Hongwen <span class="zh">王洪文</span></h1>
        <p>Give a song a new voice, or turn your words into speech.<br>
        Create AI interpretations inspired by archival recordings.</p></div>''')
        if os.getenv("VOICE_STUDIO_DESKTOP") == "1":
            gr.Markdown("**First use:** the app downloads its AI models when you generate audio. Keep the launcher open while using Voice Studio.", elem_classes="note")
        with gr.Tabs():
            with gr.Tab("Sing a song", id="sing"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=6):
                        gr.Markdown("### Your song", elem_classes="panel-title")
                        upload = gr.File(label="Drop an audio or video file", file_types=[".mp3", ".wav", ".m4a", ".mp4", ".flac", ".ogg", ".webm", ".mov", ".aac", ".mkv"], type="filepath")
                        gr.Markdown(f"Up to {MAX_SECONDS // 60} minutes · {MAX_MB} MB. Start with a song that already has vocals.", elem_classes="note")
                        with gr.Accordion("Voice & mix", open=True):
                            vocals = gr.Slider(-2, 9, value=4.5, step=.5, label="Lead vocal level (dB)", info="Bring the lead forward over the backing track.")
                            music = gr.Slider(-12, 3, value=-1.5, step=.5, label="Instrumental level (dB)")
                            quality = gr.Dropdown(choices=[("Quick", 20), ("Standard", 40), ("Detailed", 60)], value=40, label="Conversion quality")
                            video = gr.Checkbox(value=True, label="Also export MP4 when the upload contains video")
                        gr.Markdown("Original melody and pitch · Gentle vocal clarity boost · Instrumental ducks slightly while singing", elem_classes="note")
                        with gr.Row():
                            convert = gr.Button("Create AI cover", variant="primary", scale=3)
                            cancel_song = gr.Button("Stop", scale=1)
                    with gr.Column(scale=5):
                        gr.Markdown("### Your cover", elem_classes="panel-title")
                        song_status = gr.Textbox(label="Status", value="Upload a song to begin.", interactive=False)
                        song_audio = gr.Audio(label="AI cover preview", type="filepath", interactive=False)
                        with gr.Row():
                            song_wav = gr.DownloadButton(label="Download WAV · lossless")
                            song_mp3 = gr.DownloadButton(label="Download MP3 · 320 kbps")
                        song_video = gr.DownloadButton(label="Download MP4 · video with AI vocals")
                        with gr.Accordion("Generation details", open=False):
                            song_details = gr.DownloadButton(label="Download generation details · JSON")
            with gr.Tab("Text to speech", id="speech"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=6):
                        gr.Markdown("### Your words", elem_classes="panel-title")
                        text = gr.Textbox(label="Text to read", placeholder="输入你想让他说的话……", lines=8, max_lines=14)
                        gr.Markdown(f"Up to {MAX_TEXT} characters. Chinese is closest to the reference's original speech.", elem_classes="note")
                        language = gr.Dropdown(LANGUAGES, value="Chinese", label="Language")
                        gr.Examples(examples=[["大家好，欢迎来到语音工作室。今天我们一起来听一首歌。", "Chinese"], ["Hello, and welcome to the voice studio. This is an AI-generated demonstration.", "English"]], inputs=[text, language])
                        with gr.Row():
                            read = gr.Button("Generate speech", variant="primary", scale=3)
                            cancel_speech = gr.Button("Stop", scale=1)
                    with gr.Column(scale=5):
                        gr.Markdown("### Your speech", elem_classes="panel-title")
                        speech_status = gr.Textbox(label="Status", value="Enter text to begin.", interactive=False)
                        speech_audio = gr.Audio(label="AI speech preview", type="filepath", interactive=False)
                        with gr.Row():
                            speech_wav = gr.DownloadButton(label="Download WAV · lossless")
                            speech_mp3 = gr.DownloadButton(label="Download MP3 · 320 kbps")
                        with gr.Accordion("Generation details", open=False):
                            speech_details = gr.DownloadButton(label="Download generation details · JSON")
        gr.Markdown("**AI-generated voice interpretation.** These outputs are synthetic, and are not authentic Wang Hongwen recordings. Voice similarity varies with the song, text, and archival reference quality. Downloads are temporary; save your results.", elem_classes="note")
        song_event = convert.click(singing, [upload, vocals, music, quality, video],
                                  [song_audio, song_wav, song_mp3, song_video, song_details, song_status],
                                  concurrency_limit=1, concurrency_id="gpu", api_name="sing")
        speech_event = read.click(speech, [text, language], [speech_audio, speech_wav, speech_mp3, speech_details, speech_status],
                                 concurrency_limit=1, concurrency_id="gpu", api_name="speak")
        cancel_song.click(fn=lambda: "Stopped. You can start a new generation.", outputs=song_status,
                          cancels=[song_event], queue=False, api_name=False)
        cancel_speech.click(fn=lambda: "Stopped. You can start a new generation.", outputs=speech_status,
                            cancels=[speech_event], queue=False, api_name=False)
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
