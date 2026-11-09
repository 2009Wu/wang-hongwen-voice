"""Deployment settings; no model imports in the web process."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
JOBS = Path(os.getenv("JOB_ROOT", str(Path(tempfile.gettempdir()) / "wang-voice-jobs"))).resolve()
CACHE = Path(os.getenv("MODEL_CACHE", str(ROOT / ".cache"))).resolve()
SING_PYTHON = os.getenv("SING_PYTHON", sys.executable)
TTS_PYTHON = os.getenv("TTS_PYTHON", sys.executable)
MAX_SECONDS = int(os.getenv("MAX_SONG_SECONDS", "600"))
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
MAX_TEXT = int(os.getenv("MAX_TEXT_CHARS", "600"))
JOB_TIMEOUT = int(os.getenv("JOB_TIMEOUT_SECONDS", "7200"))
RETENTION = int(os.getenv("RESULT_TTL_SECONDS", "3600"))
LANGUAGES = ["Chinese", "English", "Auto", "Japanese", "Korean", "French", "German", "Spanish", "Portuguese", "Italian", "Russian"]
