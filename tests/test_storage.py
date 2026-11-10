"""Storage maintenance must preserve inference files and refuse linked paths."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('compact_runtime', ROOT / 'windows/compact_runtime.py')
compact_runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compact_runtime)


class StorageTests(unittest.TestCase):
    def test_unused_demo_assets_only_and_repair_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            remove = ['.runtime/python/tools/Lib/site-packages/torch/include/c10/test.h',
                      '.runtime/speech/Lib/site-packages/gradio/templates/frontend/app.js',
                      '.runtime/speech/Lib/site-packages/gradio/templates/node/server.js',
                      '.runtime/ffmpeg/pinned/doc/ffmpeg.html']
            keep = ['.runtime/ui/Lib/site-packages/gradio/templates/frontend/app.js',
                    '.runtime/speech/Lib/site-packages/gradio/templates/frontend/LICENSE.txt',
                    '.runtime/python/tools/Lib/site-packages/torch/include/NOTICE',
                    '.runtime/pycache/existing.pyc', '.cache/huggingface/model.safetensors']
            for name in remove + keep:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'keep or remove')
            self.assertEqual(set(compact_runtime.compact(root)['removed']), set(remove))
            self.assertTrue(all((root / name).read_bytes() == b'keep or remove' for name in keep))
            restored = root / remove[0]
            restored.write_bytes(b'from repair')
            self.assertTrue(compact_runtime.compact(root, once=True)['already_done'])
            self.assertTrue(restored.exists())
            self.assertEqual(compact_runtime.compact(root)['removed'], [remove[0]])

    def test_only_build_libraries_and_player_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            remove = ['.runtime/python/tools/Lib/site-packages/torch/lib/dnnl.lib',
                      '.runtime/ffmpeg/pinned/bin/ffplay.exe']
            keep = ['.runtime/python/tools/Lib/site-packages/torch/lib/torch_cuda.dll',
                    '.runtime/ffmpeg/pinned/bin/ffmpeg.exe',
                    '.runtime/ffmpeg/pinned/bin/ffprobe.exe',
                    '.runtime/pycache/model.pyc', '.cache/huggingface/model.safetensors',
                    'my-recording.mp4']
            for name in remove + keep:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'unchanged')
            preview = compact_runtime.compact(root, True)
            self.assertEqual(preview['bytes'], 18)
            self.assertTrue(all((root / name).exists() for name in remove))
            result = compact_runtime.compact(root)
            self.assertEqual(set(result['removed']), set(remove))
            self.assertTrue(all((root / name).read_bytes() == b'unchanged' for name in keep))
            self.assertEqual(compact_runtime.compact(root)['bytes'], 0)

    def test_linked_torch_tree_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'app'
            outside = Path(folder) / 'outside'
            outside.mkdir(); (outside / 'dnnl.lib').write_bytes(b'keep')
            parent = root / '.runtime/python/tools/Lib/site-packages/torch'
            parent.mkdir(parents=True)
            try:
                (parent / 'lib').symlink_to(outside, target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(parent / 'lib'), str(outside)],
                               check=True, capture_output=True)
            try:
                self.assertEqual(compact_runtime.compact(root)['bytes'], 0)
                self.assertEqual((outside / 'dnnl.lib').read_bytes(), b'keep')
            finally:
                if os.name == 'nt':
                    os.rmdir(parent / 'lib')
                else:
                    (parent / 'lib').unlink()


if __name__ == '__main__':
    unittest.main()
