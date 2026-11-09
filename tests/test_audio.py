import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_utils import decode_input, export_flac, fade_weights, master, mix_tracks, probe, restore_dynamics, split_text, windows


class AudioTests(unittest.TestCase):
    def test_chunk_boundaries_reconstruct_without_gaps_or_duplicate_tail(self):
        for length in [1, 38, 40, 41, 79, 80, 95]:
            chunks = list(windows(length, 40, 2))
            weight, total = np.zeros(length), np.zeros(length)
            x = np.arange(length, dtype="float32") + 1
            for i, (start, end) in enumerate(chunks):
                fade = fade_weights(end - start, 2, i == 0, i == len(chunks) - 1)
                weight[start:end] += fade
                total[start:end] += x[start:end] * fade
            self.assertTrue(np.all(weight > 0))
            np.testing.assert_allclose(total / weight, x)
            self.assertEqual(chunks[-1][1], length)
            self.assertEqual(len([end for _, end in chunks if end == length]), 1)

    def test_mix_preserves_backing_stereo_and_centers_voice(self):
        count = 44100
        voice = np.ones(count, dtype="float32") * .02
        source = np.ones(count, dtype="float32") * .1
        music = np.column_stack([np.ones(count) * .03, np.ones(count) * -.03])
        mixed = mix_tracks(voice, source, music, 44100)
        # Music is opposite-phase, so its mean cancels. Centered voice remains.
        np.testing.assert_allclose(mixed.mean(axis=1), voice * 10 ** (4.5 / 20), rtol=1e-6)
        self.assertTrue(np.all(mixed[:, 0] > mixed[:, 1]))

    def test_silence_does_not_acquire_hallucinated_vocals(self):
        silence = np.zeros(10000, dtype="float32")
        voice = np.ones_like(silence) * .1
        np.testing.assert_array_equal(restore_dynamics(voice, silence, 16000), silence)

    def test_text_chunking_never_loses_or_duplicates_words(self):
        for text in ["你好！今天我们一起听一首歌。" * 45, "Hello, world. " * 100, "字" * 253, "。！？"]:
            parts = split_text(text)
            self.assertEqual("".join(parts), text.strip())
            self.assertTrue(all(0 < len(p) <= 100 for p in parts))

    def test_media_validation_and_mastering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rate = 44100
            signal = .1 * np.sin(2 * np.pi * 440 * np.arange(rate * 2) / rate)
            sf.write(root / "input.wav", np.column_stack([signal, signal]), rate)
            _, count, actual_rate = decode_input(root / "input.wav", root / "decoded.wav", 5, 10)
            self.assertEqual((count, actual_rate), (rate * 2, rate))
            with self.assertRaisesRegex(ValueError, "limit"):
                decode_input(root / "input.wav", root / "long.wav", 1, 10)
            master(root / "decoded.wav", root / "master.wav")
            export_flac(root / "master.wav", root / "master.flac")
            wav_pcm, wav_rate = sf.read(root / "master.wav", dtype="int32", always_2d=True)
            flac_pcm, flac_rate = sf.read(root / "master.flac", dtype="int32", always_2d=True)
            self.assertEqual(wav_rate, flac_rate)
            np.testing.assert_array_equal(wav_pcm, flac_pcm)
            mastered, actual_rate = sf.read(root / "master.wav", always_2d=True)
            self.assertEqual(len(mastered), count)
            self.assertTrue(np.isfinite(mastered).all())
            self.assertLess(np.abs(mastered).max(), 1)
            (root / "invalid.mp3").write_text("not audio")
            with self.assertRaises(ValueError):
                probe(root / "invalid.mp3")


if __name__ == "__main__":
    unittest.main()
