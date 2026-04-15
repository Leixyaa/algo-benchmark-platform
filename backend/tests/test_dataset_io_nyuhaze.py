# -*- coding: utf-8 -*-
"""RESIDE SOTS indoor (nyuhaze500)：多雾图共用一个 GT 时的配对与计数。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.vision.dataset_io import _pair_token_full, count_paired_images


class TestNyuhazePairing(unittest.TestCase):
    def test_pair_token_matches_scene_id(self) -> None:
        self.assertEqual(_pair_token_full("1400_1.png"), "1400")
        self.assertEqual(_pair_token_full("1400_10.png"), "1400")
        self.assertEqual(_pair_token_full("1400.png"), "1400")

    def test_count_allows_multiple_hazy_per_gt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ds = root / "ds_nyuhaze_smoke"
            (ds / "hazy").mkdir(parents=True)
            (ds / "gt").mkdir()
            (ds / "gt" / "1400.png").write_bytes(b"x")
            for i in (1, 2, 3):
                (ds / "hazy" / f"1400_{i}.png").write_bytes(b"x")
            n = count_paired_images(root, "", "ds_nyuhaze_smoke", "hazy", "gt")
            self.assertEqual(n, 3)


if __name__ == "__main__":
    unittest.main()
