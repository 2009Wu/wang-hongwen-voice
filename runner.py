"""Bounded worker orchestration for the public web interface."""
import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from settings import CACHE, JOBS, JOB_TIMEOUT, RETENTION, ROOT, SING_PYTHON, TTS_PYTHON

GPU_LOCK = threading.Lock()


def cleanup_old_jobs():
    JOBS.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for directory in JOBS.iterdir():
        # Only directories created by this app; never follow symlinks out of JOBS.
        if directory.is_symlink() or not directory.is_dir() or len(directory.name) != 32:
            continue
        if any(c not in "0123456789abcdef" for c in directory.name):
            continue
        marker = directory / ".finished"
        if marker.exists() and now - marker.stat().st_mtime > RETENTION:
            shutil.rmtree(directory)


def stop_worker(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, timeout=15)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=15)


def readable_error(log):
    tail = "\n".join(log)
    if "CUDA out of memory" in tail or "OutOfMemoryError" in tail:
        return "The GPU ran out of memory. Restart the Space or select a GPU with more memory."
    if "A CUDA GPU is required" in tail:
        if os.getenv("VOICE_STUDIO_DESKTOP") == "1":
            return "Update the NVIDIA graphics driver, restart Windows, and use Repair setup in the launcher."
        return "Select GPU hardware in the Space Settings, then restart the Space."
    if any(x in tail for x in ["ConnectionError", "LocalEntryNotFoundError", "ReadTimeout", "HTTPError", "HfHubHTTPError"]):
        return "A model download failed. Check the Space's internet access and try again; completed downloads are cached."
    for line in reversed(log):
        if line.startswith(("ValueError: ", "RuntimeError: ")):
            return line.split(": ", 1)[1][:300]
    return "Generation failed. The Space owner can check the runtime logs for details."


def run_job(request):
    """Yield (progress, message, result). Closing the generator stops its GPU process."""
    with GPU_LOCK:
        cleanup_old_jobs()
        job = JOBS / uuid.uuid4().hex
        job.mkdir()
        request_path = job / "request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        python = SING_PYTHON if request["mode"] == "sing" else TTS_PYTHON
        env = os.environ.copy()
        env["MODEL_CACHE"] = str(CACHE)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        lines, log = queue.Queue(), deque(maxlen=60)
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = None
        try:
            process = subprocess.Popen([python, "-u", str(ROOT / "worker.py"), str(request_path)],
                                       cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", **options)

            def reader():
                for line in process.stdout:
                    lines.put(line.rstrip())
                lines.put(None)

            threading.Thread(target=reader, daemon=True).start()
            started, last_update, fraction, message = time.monotonic(), 0, 0, "Starting the voice engine…"
            while True:
                if time.monotonic() - started > JOB_TIMEOUT:
                    raise TimeoutError("Generation timed out. Try a shorter song or text.")
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    line = ""
                if line is None:
                    break
                if line.startswith("@@PROGRESS "):
                    update = json.loads(line[len("@@PROGRESS "):])
                    fraction, message = update["fraction"], update["message"]
                    yield fraction, message, None
                    last_update = time.monotonic()
                elif line:
                    log.append(line)
                if time.monotonic() - last_update > 15:
                    yield fraction, message + f" ({int(time.monotonic() - started)}s elapsed)", None
                    last_update = time.monotonic()
            process.wait(timeout=15)
            if process.returncode:
                print("Worker failed:\n" + "\n".join(log), flush=True)
                raise RuntimeError(readable_error(log))
            result = json.loads((job / "result.json").read_text(encoding="utf-8"))
            for key in ["audio", "wav", "video", "details"]:
                if result[key] and not Path(result[key]).is_relative_to(job / "results"):
                    raise RuntimeError("Unexpected output path")
            yield 1, f"Ready · {result['elapsed_seconds']:.0f}s · AI-generated", result
        finally:
            if process:
                stop_worker(process)
                if process.stdout:
                    process.stdout.close()
            # Keep only deliverables; remove the uploaded decode, text, stems, and chunk files.
            for item in job.iterdir():
                if item.name != "results":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink(missing_ok=True)
            (job / ".finished").touch()
