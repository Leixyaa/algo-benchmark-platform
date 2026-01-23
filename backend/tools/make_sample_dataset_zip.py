# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import io
import os
import zipfile
from pathlib import Path

import cv2
import numpy as np


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _png_bytes(img_bgr_u8: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img_bgr_u8)
    if not ok:
        raise RuntimeError("png_encode_failed")
    return bytes(buf)


def _make_gt(seed: int, h: int = 360, w: int = 640) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.random((h, w, 3), dtype=np.float32)
    gx = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    gy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    gt = 0.55 * base + 0.25 * gx + 0.20 * gy
    gt = np.clip(gt, 0, 1)
    return (gt * 255.0 + 0.5).astype(np.uint8)


def _apply_haze(gt_bgr_u8: np.ndarray) -> np.ndarray:
    h, w = gt_bgr_u8.shape[:2]
    gt = gt_bgr_u8.astype(np.float32) / 255.0
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    t = 0.35 + 0.55 * (1 - y)
    t = np.clip(t, 0.15, 0.95)[:, :, None]
    A = np.array([0.92, 0.92, 0.92], dtype=np.float32)[None, None, :]
    hazy = gt * t + A * (1 - t)
    return (np.clip(hazy, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def _apply_noise(gt_bgr_u8: np.ndarray, sigma: float = 12.0) -> np.ndarray:
    x = gt_bgr_u8.astype(np.float32)
    n = np.random.normal(0.0, float(sigma), size=x.shape).astype(np.float32)
    y = np.clip(x + n, 0, 255)
    return y.astype(np.uint8)


def _apply_blur(gt_bgr_u8: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(gt_bgr_u8, (0, 0), sigmaX=1.2)


def _apply_lr(gt_bgr_u8: np.ndarray, scale: int = 2) -> np.ndarray:
    h, w = gt_bgr_u8.shape[:2]
    nh, nw = max(8, h // scale), max(8, w // scale)
    return cv2.resize(gt_bgr_u8, (nw, nh), interpolation=cv2.INTER_AREA)


def _apply_dark(gt_bgr_u8: np.ndarray, gamma: float = 2.0) -> np.ndarray:
    g = max(0.05, float(gamma))
    x = gt_bgr_u8.astype(np.float32) / 255.0
    y = np.clip(np.power(x, g), 0.0, 1.0)
    return (y * 255.0 + 0.5).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path("backend") / "outputs" / "sample_ds_demo.zip"))
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260123)
    args = ap.parse_args()

    out_path = Path(args.out).resolve()
    _ensure_dir(out_path.parent)

    cnt = max(1, int(args.count))
    seed0 = int(args.seed)

    dirs = {
        "gt": lambda gt: gt,
        "hazy": _apply_haze,
        "noisy": _apply_noise,
        "blur": _apply_blur,
        "lr": _apply_lr,
        "dark": _apply_dark,
    }

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i in range(cnt):
            name = f"{i:03d}.png"
            gt = _make_gt(seed0 + i)
            for dname, fn in dirs.items():
                img = fn(gt)
                zf.writestr(f"{dname}/{name}", _png_bytes(img))

        readme = "\n".join(
            [
                "sample dataset zip for algo-benchmark-platform",
                "",
                "Expected layout:",
                "  gt/   : ground-truth images (png/jpg/...)",
                "  hazy/ : dehaze inputs",
                "  noisy/: denoise inputs",
                "  blur/ : deblur inputs",
                "  lr/   : super-resolution low-res inputs",
                "  dark/ : lowlight inputs",
                "",
                "Pairing rule: filenames should match between input dir and gt/",
            ]
        )
        zf.writestr("README.txt", readme.encode("utf-8"))

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

