import argparse
import os
import sys
import cv2
import numpy as np


def soft_threshold(x: np.ndarray, thresh: float) -> np.ndarray:
    return np.sign(x) * np.maximum(np.abs(x) - thresh, 0.0)


def haar_dwt2(channel: np.ndarray):
    # channel: float32, even H/W
    a = channel[0::2, 0::2]
    b = channel[0::2, 1::2]
    c = channel[1::2, 0::2]
    d = channel[1::2, 1::2]

    ll = (a + b + c + d) * 0.5
    lh = (a - b + c - d) * 0.5
    hl = (a + b - c - d) * 0.5
    hh = (a - b - c + d) * 0.5
    return ll, lh, hl, hh


def haar_idwt2(ll, lh, hl, hh):
    h, w = ll.shape
    out = np.zeros((h * 2, w * 2), dtype=np.float32)
    out[0::2, 0::2] = (ll + lh + hl + hh) * 0.5
    out[0::2, 1::2] = (ll - lh + hl - hh) * 0.5
    out[1::2, 0::2] = (ll + lh - hl - hh) * 0.5
    out[1::2, 1::2] = (ll - lh - hl + hh) * 0.5
    return out


def denoise_channel(channel_u8: np.ndarray) -> np.ndarray:
    ch = channel_u8.astype(np.float32)
    h0, w0 = ch.shape
    pad_h = h0 % 2
    pad_w = w0 % 2
    if pad_h or pad_w:
        ch = np.pad(ch, ((0, pad_h), (0, pad_w)), mode="reflect")

    ll, lh, hl, hh = haar_dwt2(ch)

    sigma = np.median(np.abs(hh)) / 0.6745 if hh.size > 0 else 0.0
    thresh = sigma * np.sqrt(2.0 * np.log(ch.size + 1.0))

    lh = soft_threshold(lh, thresh)
    hl = soft_threshold(hl, thresh)
    hh = soft_threshold(hh, thresh)

    rec = haar_idwt2(ll, lh, hl, hh)
    rec = rec[:h0, :w0]
    rec = np.clip(rec, 0, 255).astype(np.uint8)
    return rec


def wavelet_denoise_bgr(img_bgr_u8: np.ndarray) -> np.ndarray:
    channels = cv2.split(img_bgr_u8)
    out_channels = [denoise_channel(ch) for ch in channels]
    out = cv2.merge(out_channels)
    return out


def main():
    parser = argparse.ArgumentParser(description="Wavelet soft-threshold image denoising")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    args = parser.parse_args()

    img = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read input image: {args.input}", file=sys.stderr)
        sys.exit(1)

    out = wavelet_denoise_bgr(img)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok = cv2.imwrite(args.output, out)
    if not ok:
        print(f"Failed to write output image: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
