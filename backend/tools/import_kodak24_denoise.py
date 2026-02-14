# -*- coding: gb18030 -*-
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np


def _list_images(d: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts], key=lambda p: p.name)


def _ensure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)


def _read_color(p: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"read failed: {p}")
    return img


def _write_png(p: Path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"encode failed: {p}")
    p.write_bytes(buf.tobytes())


def _gaussian_noisy(img_bgr: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    x = img_bgr.astype(np.float32)
    n = rng.normal(0.0, sigma, size=x.shape).astype(np.float32)
    y = np.clip(x + n, 0.0, 255.0).astype(np.uint8)
    return y


def _post_json(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _patch_json(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    src_gt = project_root / "数据集" / "去噪" / "kodak24" / "gt"
    if not src_gt.exists():
        raise SystemExit(f"source not found: {src_gt}")

    imgs = _list_images(src_gt)
    if not imgs:
        raise SystemExit(f"no images under: {src_gt}")

    dataset_id = "ds_kodak24_denoise"
    dest_root = project_root / "backend" / "data" / dataset_id
    dest_gt = dest_root / "gt"
    dest_noisy = dest_root / "noisy"
    _ensure_dir(dest_gt)
    _ensure_dir(dest_noisy)

    rng = np.random.default_rng(20260207)
    sigma = 25.0
    count = 0
    for i, p in enumerate(imgs):
        img = _read_color(p)
        out_name = f"{i:03d}.png"
        _write_png(dest_gt / out_name, img)
        _write_png(dest_noisy / out_name, _gaussian_noisy(img, sigma=sigma, rng=rng))
        count += 1

    print(f"written_pairs={count} dataset_id={dataset_id} sigma={sigma}")
    print(f"dest={dest_root}")

    base = "http://127.0.0.1:8000"
    try:
        urllib.request.urlopen(base + "/health", timeout=2).read()
    except Exception:
        print("backend_not_running: skip register/scan")
        return

    payload = {"dataset_id": dataset_id, "name": "Kodak24(合成高斯噪声)", "type": "图像", "size": f"{count} 张"}
    try:
        _post_json(base + "/datasets", payload)
    except urllib.error.HTTPError:
        _patch_json(base + f"/datasets/{dataset_id}", {"name": payload["name"], "type": payload["type"], "size": payload["size"]})

    _post_json(base + f"/datasets/{dataset_id}/scan", {})
    time.sleep(0.2)
    print("registered_and_scanned")


if __name__ == "__main__":
    main()
