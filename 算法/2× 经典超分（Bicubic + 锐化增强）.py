import argparse
import os
import sys
import cv2
import numpy as np


def unsharp_mask(img_bgr_u8: np.ndarray, sigma: float = 1.0, amount: float = 1.2) -> np.ndarray:
    img = img_bgr_u8.astype(np.float32)
    blur = cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, sigmaY=sigma)
    sharp = img + amount * (img - blur)
    sharp = np.clip(sharp, 0, 255)
    return sharp.astype(np.uint8)


def super_resolve(img_bgr_u8: np.ndarray, scale: int = 2) -> np.ndarray:
    h, w = img_bgr_u8.shape[:2]
    up = cv2.resize(img_bgr_u8, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    # 只在亮度通道锐化，减少色彩噪声放大
    ycrcb = cv2.cvtColor(up, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    y = unsharp_mask(y[..., None].repeat(3, axis=2), sigma=1.0, amount=1.0)[:, :, 0]
    out = cv2.merge([y, cr, cb])
    out = cv2.cvtColor(out, cv2.COLOR_YCrCb2BGR)
    return out


def main():
    parser = argparse.ArgumentParser(description="2x classical super-resolution by bicubic + sharpen")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    args = parser.parse_args()

    img = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read input image: {args.input}", file=sys.stderr)
        sys.exit(1)

    out = super_resolve(img, scale=2)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok = cv2.imwrite(args.output, out)
    if not ok:
        print(f"Failed to write output image: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
