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
from studio_library import archive, stash_request
from studio_paths import STATE, atomic_json

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
        return "显存不足 / CUDA out of memory：关闭游戏等占用显卡的程序，在高级选项选择「6 GB 节省显存」再试。"
    if any(x in tail for x in ['No space left on device', 'There is not enough space', '磁盘空间不足', 'WinError 112']):
        return '磁盘空间不足：请清理磁盘，或将作品目录和模型缓存移动到空间足够的位置后重试。'
    if 'PermissionError' in tail:
        return '无法写入文件：请把程序解压到自己有写入权限的文件夹，并检查作品目录是否被其他程序占用。'
    if "A CUDA GPU is required" in tail:
        if os.getenv("VOICE_STUDIO_DESKTOP") == "1":
            return "请更新 NVIDIA 驱动、重启电脑，再在启动器点击「修复安装」。"
        return "Select GPU hardware in the Space Settings, then restart the Space."
    if any(x in tail for x in ["ConnectionError", "LocalEntryNotFoundError", "ReadTimeout", "HTTPError", "HfHubHTTPError"]):
        return "模型下载失败：请检查网络后重试，已完成的下载会保留；不要删除模型缓存。"
    for line in reversed(log):
        if line.startswith(("ValueError: ", "RuntimeError: ")):
            return line.split(": ", 1)[1][:300]
    return "生成失败，请查看启动器的运行日志后重试。"


def run_job(request):
    """Yield (progress, message, result). Closing the generator stops its GPU process."""
    with GPU_LOCK:
        if (ROOT / '.runtime/update-request.json').exists():
            raise RuntimeError('正在准备更新，请稍后重新打开工作室。')
        cleanup_old_jobs()
        job = JOBS / uuid.uuid4().hex
        job.mkdir()
        request_path = job / "request.json"
        python = SING_PYTHON if request["mode"] == "sing" else TTS_PYTHON
        env = os.environ.copy()
        env["MODEL_CACHE"] = str(CACHE)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        lines, log = queue.Queue(), deque(maxlen=60)
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = None
        archived = False
        try:
            request = stash_request(request, job)
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            process = subprocess.Popen([python, "-u", str(ROOT / "worker.py"), str(request_path)],
                                       cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", **options)

            def reader():
                for line in process.stdout:
                    lines.put(line.rstrip())
                lines.put(None)

            threading.Thread(target=reader, daemon=True).start()
            started, last_update, fraction, message = time.monotonic(), 0, 0, "正在启动语音引擎…"
            while True:
                if time.monotonic() - started > JOB_TIMEOUT:
                    raise TimeoutError("生成超时：请先试听短片段，或缩短文字后重试。")
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
            for key in ["audio", "wav", "video", "details"] + (["flac"] if "flac" in result else []):
                if result[key] and not Path(result[key]).is_relative_to(job / "results"):
                    raise RuntimeError("Unexpected output path")
            result = archive(request, result, job)
            archived = True
            yield 1, f"已自动保存 · {result['elapsed_seconds']:.0f} 秒 · AI 生成", result
        except GeneratorExit:
            if process: stop_worker(process)
            if not archived:
                try: archive(request, None, job, failure='已停止，可在作品历史中重试。'); archived = True
                except Exception: pass
            raise
        except Exception as error:
            if process: stop_worker(process)
            atomic_json(STATE / 'last-error.json', {'type': type(error).__name__, 'message': readable_error(log) if log else str(error)[:300], 'time': time.time()})
            if not archived:
                try: archive(request, None, job, failure=str(error)); archived = True
                except Exception: pass
            raise
        finally:
            if process:
                stop_worker(process)
                if process.stdout:
                    process.stdout.close()
            # Keep only deliverables; remove the uploaded decode, text, stems, and chunk files.
            for item in list(job.iterdir()) if archived else []:
                if item.name != "results":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink(missing_ok=True)
            if archived: (job / ".finished").touch()
