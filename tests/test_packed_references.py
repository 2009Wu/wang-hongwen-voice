import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('restore_references', ROOT / 'windows/restore_references.py')
restore_references = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_references)


class ReferencePackingTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv('FFMPEG') or shutil.which('ffmpeg'), 'FFmpeg required')
    def test_restore_exact_wav_and_reject_corrupt_payload(self):
        with tempfile.TemporaryDirectory(prefix='reference test ') as folder:
            root = Path(folder)
            (root / 'assets').mkdir()
            items = json.loads((ROOT / 'assets/packed-references.json').read_text())['files']
            shutil.copy2(ROOT / 'assets/packed-references.json', root / 'assets')
            for item in items:
                shutil.copy2(ROOT / 'assets' / item['flac'], root / 'assets')
            tool = os.getenv('FFMPEG') or shutil.which('ffmpeg')
            self.assertEqual(restore_references.restore(root, tool), 2)
            for item in items:
                self.assertEqual((root / 'assets' / item['wav']).read_bytes(),
                                 (ROOT / 'assets' / item['wav']).read_bytes())
            self.assertEqual(restore_references.restore(root, tool), 0)
            target = root / 'assets' / items[0]['wav']
            target.unlink()
            (root / 'assets' / items[0]['flac']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                restore_references.restore(root, tool)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
