import argparse
import os
import sys
import cv2
import numpy as np


def gaussian_kernel(ksize: int = 9, sigma: float = 2.0) -> np.ndarray:
    ax = np.arange(-(ksize // 2), ksize // 2 + 1, dtype=np.float32)
    xx, yy = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx * xx + yy * yy) / (2.0 * sigma * sigma))
    kernel /= np.sum(kernel)
    return kernel.astype(np.float32)


def psf2otf(psf: np.ndarray, shape) -> np.ndarray:
    otf = np.zeros(shape, dtype=np.float32)
    kh, kw = psf.shape
    otf[:kh, :kw] = psf
    otf = np.roll(otf, -kh // 2, axis=0)
    otf = np.roll(otf, -kw // 2, axis=1)
    return np.fft.fft2(otf)


def wiener_deblur_channel(channel_u8: np.ndarray, ksize: int = 9, sigma: float = 2.0, k: float = 0.01) -> np.ndarray:
    img = channel_u8.astype(np.float32) / 255.0
    psf = gaussian_kernel(ksize=ksize, sigma=sigma)
    H = psf2otf(psf, img.shape)
    G = np.fft.fft2(img)
    H_conj = np.conj(H)
    F_hat = (H_conj / (np.abs(H) ** 2 + k)) * G
    rec = np.real(np.fft.ifft2(F_hat))
    rec = np.clip(rec, 0.0, 1.0)
    return (rec * 255.0 + 0.5).astype(np.uint8)


def deblur_bgr(img_bgr_u8: np.ndarray) -> np.ndarray:
    out_channels = [wiener_deblur_channel(ch) for ch in cv2.split(img_bgr_u8)]
    out = cv2.merge(out_channels)
    # 轻度去振铃与锐化平衡
    out = cv2.GaussianBlur(out, (0, 0), 0.3)
    return out


def main():
    parser = argparse.ArgumentParser(description="Wiener deconvolution deblurring")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    args = parser.parse_args()

    img = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read input image: {args.input}", file=sys.stderr)
        sys.exit(1)

    out = deblur_bgr(img)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok = cv2.imwrite(args.output, out)
    if not ok:
        print(f"Failed to write output image: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
