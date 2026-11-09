"""Run with the UI environment; no model downloads or GPU jobs."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import app
except ImportError:
    app = None


@unittest.skipIf(app is None, "Requires the UI environment")
class SimpleInputTests(unittest.TestCase):
    def test_ambiguous_input_is_rejected_instead_of_silently_discarded(self):
        for text, upload in [("", None), ("你好", "song.wav")]:
            with self.assertRaises(ValueError):
                app.make_request(text, upload)

    def test_text_and_audio_route_without_mode_selection(self):
        self.assertEqual(app.make_request("  你好  ", None)["text"], "你好")
        with tempfile.NamedTemporaryFile(suffix=".mp3") as song:
            request = app.make_request("", song.name)
        self.assertEqual(request["mode"], "sing")
        self.assertEqual(request["steps"], 40)
        self.assertEqual(request["performance"], "auto")

    def test_legacy_endpoints_and_single_generate_endpoint_are_present(self):
        demo = app.build_app()
        names = {item.get("api_name") for item in demo.config["dependencies"]}
        self.assertTrue({"generate", "sing", "speak"}.issubset(names))
