import argparse
import os
import sys
from collections import deque

import cv2
import numpy as np


def temporal_denoise(frames: list[np.ndarray]) -> np.ndarray:
    """Simple temporal denoising by averaging aligned neighboring frames.

    This is a lightweight, classical video denoising baseline. It does not rely on
    deep learning and is suitable for validating a video-processing pipeline.
    """
    if len(frames) == 1:
        return frames[0]

    stack = np.stack([f.astype(np.float32) for f in frames], axis=0)
    avg = np.mean(stack, axis=0)
    out = np.clip(avg, 0, 255).astype(np.uint8)
    return out


def process_video(input_path: str, output_path: str, radius: int = 2) -> None:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25.0

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot open output video for writing: {output_path}")

    window = deque()
    buffered = []

    # Preload the first few frames.
    for _ in range(radius + 1):
        ok, frame = cap.read()
        if not ok:
            break
        window.append(frame)

    processed = 0
    while window:
        # Fill the right side of the window to target size.
        while len(window) < 2 * radius + 1:
            ok, frame = cap.read()
            if not ok:
                break
            window.append(frame)

        denoised = temporal_denoise(list(window))
        out.write(denoised)
        processed += 1

        window.popleft()

    cap.release()
    out.release()

    if processed == 0:
        raise RuntimeError("No frames were processed. Please check the input video.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple temporal video denoising baseline")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--radius", type=int, default=2, help="Temporal radius, default=2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        process_video(args.input, args.output, radius=max(0, args.radius))
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
