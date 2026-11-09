import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from performance import choose_profile


class HardwarePolicyTests(unittest.TestCase):
    def test_six_gb_is_supported_but_four_gb_is_not(self):
        self.assertEqual(choose_profile(6144, 5600), "low")
        with self.assertRaises(ValueError):
            choose_profile(4096, 4000)

    def test_free_memory_overrides_manual_large_profile(self):
        self.assertEqual(choose_profile(16384, 5000, "fast"), "low")
        self.assertEqual(choose_profile(8192, 7600), "balanced")
        self.assertEqual(choose_profile(16384, 14500), "fast")
        self.assertEqual(choose_profile(16384, 14500, "low"), "low")
