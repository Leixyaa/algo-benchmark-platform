# backend/app/vision/dehaze_dcp.py
from __future__ import annotations

import numpy as np
import cv2


def _to_float01(img_bgr_u8: np.ndarray) -> np.ndarray:
    img = img_bgr_u8.astype(np.float32) / 255.0
    return np.clip(img, 0.0, 1.0)


def dark_channel(img_bgr01: np.ndarray, patch: int = 15) -> np.ndarray:
    # img_bgr01: float32, [0,1]
    min_rgb = np.min(img_bgr01, axis=2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (patch, patch))
    dark = cv2.erode(min_rgb, kernel)
    return dark


def estimate_atmospheric_light(img_bgr01: np.ndarray, dark: np.ndarray, top_percent: float = 0.001) -> np.ndarray:
    h, w = dark.shape
    num = max(1, int(h * w * top_percent))
    flat_dark = dark.reshape(-1)
    idx = np.argpartition(flat_dark, -num)[-num:]  # indices of brightest in dark channel
    flat_img = img_bgr01.reshape(-1, 3)
    A = np.max(flat_img[idx], axis=0)  # pick max RGB among candidates
    return A


def estimate_transmission(img_bgr01: np.ndarray, A: np.ndarray, omega: float = 0.95, patch: int = 15) -> np.ndarray:
    # t(x) = 1 - omega * dark( I(x) / A )
    normed = img_bgr01 / (A.reshape(1, 1, 3) + 1e-6)
    dark_normed = dark_channel(normed, patch=patch)
    t = 1.0 - omega * dark_normed
    return np.clip(t, 0.0, 1.0)


def guided_filter(I_gray01: np.ndarray, p: np.ndarray, r: int = 40, eps: float = 1e-3) -> np.ndarray:
    # Simple guided filter implementation (He et al. 2010 style)
    # I_gray01: guidance image in [0,1], shape (H,W)
    # p: filtering input, shape (H,W)
    I = I_gray01.astype(np.float32)
    p = p.astype(np.float32)

    ksize = (2 * r + 1, 2 * r + 1)

    mean_I = cv2.boxFilter(I, ddepth=-1, ksize=ksize)
    mean_p = cv2.boxFilter(p, ddepth=-1, ksize=ksize)
    corr_I = cv2.boxFilter(I * I, ddepth=-1, ksize=ksize)
    corr_Ip = cv2.boxFilter(I * p, ddepth=-1, ksize=ksize)

    var_I = corr_I - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = cv2.boxFilter(a, ddepth=-1, ksize=ksize)
    mean_b = cv2.boxFilter(b, ddepth=-1, ksize=ksize)

    q = mean_a * I + mean_b
    return q


def recover_radiance(img_bgr01: np.ndarray, t: np.ndarray, A: np.ndarray, t0: float = 0.1) -> np.ndarray:
    t_clip = np.maximum(t, t0)
    J = (img_bgr01 - A.reshape(1, 1, 3)) / t_clip[:, :, None] + A.reshape(1, 1, 3)
    return np.clip(J, 0.0, 1.0)


def dehaze_dcp(img_bgr_u8: np.ndarray, patch: int = 15, omega: float = 0.95, t0: float = 0.1) -> np.ndarray:
    img01 = _to_float01(img_bgr_u8)
    dark = dark_channel(img01, patch=patch)
    A = estimate_atmospheric_light(img01, dark)
    t = estimate_transmission(img01, A, omega=omega, patch=patch)

    # refine transmission with guided filter (use gray guidance)
    gray = cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    t_refined = guided_filter(gray, t, r=40, eps=1e-3)
    t_refined = np.clip(t_refined, 0.0, 1.0)

    J01 = recover_radiance(img01, t_refined, A, t0=t0)
    out_u8 = (J01 * 255.0 + 0.5).astype(np.uint8)
    return out_u8
