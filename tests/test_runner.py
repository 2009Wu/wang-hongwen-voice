import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class RunnerTests(unittest.TestCase):
    def test_cleanup_only_removes_finished_expired_app_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expired, active, foreign = root / ("a" * 32), root / ("b" * 32), root / "keep-me"
            for directory in [expired, active, foreign]:
                directory.mkdir()
            marker = expired / ".finished"
            marker.touch()
            os.utime(marker, (0, 0))
            with patch.object(runner, "JOBS", root):
                runner.cleanup_old_jobs()
            self.assertFalse(expired.exists())
            self.assertTrue(active.exists())
            self.assertTrue(foreign.exists())

    def test_cancel_stops_a_real_worker_process(self):
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen([sys.executable, "-u", "-c", "import time; print('ready',flush=True); time.sleep(120)"],
                                   stdout=subprocess.PIPE, text=True, **options)
        try:
            self.assertEqual(process.stdout.readline().strip(), "ready")
            runner.stop_worker(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
            process.stdout.close()

    def test_actionable_download_and_gpu_errors(self):
        self.assertIn("download failed", runner.readable_error(["HfHubHTTPError: unavailable"]))
        self.assertIn("GPU hardware", runner.readable_error(["RuntimeError: A CUDA GPU is required"]))
        self.assertIn("out of memory", runner.readable_error(["torch.OutOfMemoryError: CUDA out of memory"]))


if __name__ == "__main__":
    unittest.main()
