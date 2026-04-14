#!/usr/bin/env python3
"""
Minimal standalone denoise example for the controlled "algorithm access" workflow.

Task type:
    denoise

Dependencies:
    python>=3.10
    opencv-python
    numpy

Example:
    python backend/tools/sample_algorithm_denoise.py --input ./input --output ./output
    python backend/tools/sample_algorithm_denoise.py --input ./input/demo.png --output ./output
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def process_image(image: np.ndarray) -> np.ndarray:
    """
    A simple denoise baseline based on OpenCV FastNLMeans.
    """
    if image is None or image.size == 0:
        raise ValueError("invalid input image")
    return cv2.fastNlMeansDenoisingColored(
        image,
        None,
        h=10,
        hColor=10,
        templateWindowSize=7,
        searchWindowSize=21,
    )


def iter_input_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        raise FileNotFoundError(f"input path not found: {input_path}")
    return sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )


def build_output_path(source_root: Path, source_path: Path, output_root: Path) -> Path:
    if source_root.is_file():
        return output_root / source_path.name
    relative = source_path.relative_to(source_root)
    return output_root / relative


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal denoise algorithm example")
    parser.add_argument("--input", required=True, help="Input image path or directory")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    files = iter_input_images(input_path)
    if not files:
        raise RuntimeError(f"no image files found under: {input_path}")

    processed = 0
    for image_path in files:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"[skip] failed to read: {image_path}")
            continue
        result = process_image(image)
        out_path = build_output_path(input_path, image_path, output_root)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(out_path), result)
        if not ok:
            raise RuntimeError(f"failed to write result: {out_path}")
        processed += 1
        print(f"[ok] {image_path.name} -> {out_path}")

    print(f"done, processed {processed} image(s)")


if __name__ == "__main__":
    main()
