import argparse
import os
import sys
import cv2
import numpy as np


def single_scale_retinex(img_f: np.ndarray, sigma: float) -> np.ndarray:
    blur = cv2.GaussianBlur(img_f, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return np.log(img_f + 1.0) - np.log(blur + 1.0)


def msrcr(img_bgr_u8: np.ndarray) -> np.ndarray:
    img = img_bgr_u8.astype(np.float32) + 1.0
    scales = [15.0, 80.0, 250.0]

    msr = np.zeros_like(img, dtype=np.float32)
    for s in scales:
        msr += single_scale_retinex(img, s)
    msr /= float(len(scales))

    sum_rgb = np.sum(img, axis=2, keepdims=True)
    color_restore = np.log(125.0 * img) - np.log(sum_rgb + 1.0)

    out = 1.2 * (msr * color_restore)

    out_norm = np.zeros_like(out, dtype=np.float32)
    for c in range(3):
        ch = out[:, :, c]
        lo = np.percentile(ch, 1)
        hi = np.percentile(ch, 99)
        if hi <= lo:
            out_norm[:, :, c] = np.clip(ch, 0, 255)
        else:
            out_norm[:, :, c] = (ch - lo) * 255.0 / (hi - lo)

    out_norm = np.clip(out_norm, 0, 255).astype(np.uint8)
    # 轻微平滑，降低色彩噪声
    out_norm = cv2.bilateralFilter(out_norm, d=5, sigmaColor=20, sigmaSpace=20)
    return out_norm


def main():
    parser = argparse.ArgumentParser(description="MSRCR dehazing")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    args = parser.parse_args()

    img = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read input image: {args.input}", file=sys.stderr)
        sys.exit(1)

    out = msrcr(img)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok = cv2.imwrite(args.output, out)
    if not ok:
        print(f"Failed to write output image: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
