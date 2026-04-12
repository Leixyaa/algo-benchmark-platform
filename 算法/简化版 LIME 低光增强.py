import argparse
import os
import sys
import cv2
import numpy as np


def lime_enhance(img_bgr_u8: np.ndarray) -> np.ndarray:
    img = img_bgr_u8.astype(np.float32) / 255.0

    # 初始照明估计：每个像素取三个通道最大值
    t = np.max(img, axis=2)
    # 平滑照明图，避免噪声被放大
    t_smooth = cv2.GaussianBlur(t, (0, 0), sigmaX=5.0, sigmaY=5.0)
    t_smooth = np.clip(t_smooth, 1e-3, 1.0)

    gamma = 0.8
    t_refined = np.power(t_smooth, gamma)
    t_refined = np.clip(t_refined, 0.1, 1.0)

    enhanced = img / t_refined[:, :, None]
    enhanced = np.clip(enhanced, 0.0, 1.0)

    out = (enhanced * 255.0 + 0.5).astype(np.uint8)
    out = cv2.bilateralFilter(out, d=5, sigmaColor=20, sigmaSpace=20)

    # 轻微对比度拉伸
    out_f = out.astype(np.float32)
    lo = np.percentile(out_f, 1)
    hi = np.percentile(out_f, 99)
    if hi > lo:
        out_f = (out_f - lo) * 255.0 / (hi - lo)
    out_f = np.clip(out_f, 0, 255)
    return out_f.astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(description="Low-light enhancement by simplified LIME")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    args = parser.parse_args()

    img = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read input image: {args.input}", file=sys.stderr)
        sys.exit(1)

    out = lime_enhance(img)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok = cv2.imwrite(args.output, out)
    if not ok:
        print(f"Failed to write output image: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
