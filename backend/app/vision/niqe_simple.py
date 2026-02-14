# -*- coding: utf-8 -*-
from __future__ import annotations

import cv2
import numpy as np


def _to_gray_f32(img_bgr_u8: np.ndarray) -> np.ndarray:
    if img_bgr_u8.ndim == 2:
        g = img_bgr_u8
    else:
        g = cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2GRAY)
    return g.astype(np.float32)


def _mscn_coefficients(img: np.ndarray, C: float = 1.0) -> np.ndarray:
    mu = cv2.GaussianBlur(img, (7, 7), 7 / 6)
    mu_sq = mu * mu
    sigma = cv2.GaussianBlur(img * img, (7, 7), 7 / 6)
    sigma = np.sqrt(np.abs(sigma - mu_sq))
    return (img - mu) / (sigma + C)


def _agg_features(mscn: np.ndarray) -> np.ndarray:
    x = mscn.reshape(-1)
    x_mean = float(np.mean(x))
    x_var = float(np.var(x))

    eps = 1e-9
    x_std = np.sqrt(x_var) + eps
    skew = float(np.mean(((x - x_mean) / x_std) ** 3))
    kurt = float(np.mean(((x - x_mean) / x_std) ** 4))

    h_prod = (mscn[:, :-1] * mscn[:, 1:]).reshape(-1)
    v_prod = (mscn[:-1, :] * mscn[1:, :]).reshape(-1)
    hp_mean, hp_var = float(np.mean(h_prod)), float(np.var(h_prod))
    vp_mean, vp_var = float(np.mean(v_prod)), float(np.var(v_prod))

    return np.array([x_mean, x_var, skew, kurt, hp_mean, hp_var, vp_mean, vp_var], dtype=np.float32)


def niqe_score(img_bgr_u8: np.ndarray) -> float:
    if img_bgr_u8 is None:
        raise ValueError("img_is_none")

    img = np.asarray(img_bgr_u8)
    if img.size == 0:
        raise ValueError("img_is_empty")

    if img.ndim == 3 and img.shape[2] > 3:
        img = img[:, :, :3]

    if img.dtype != np.uint8:
        img = np.clip(img.astype(np.float32), 0, 255).astype(np.uint8)

    img = np.ascontiguousarray(img)
    g = _to_gray_f32(img)

    h, w = g.shape[:2]
    target_min = 256
    if min(h, w) < target_min:
        scale = target_min / float(min(h, w))
        new_w = max(8, int(w * scale))
        new_h = max(8, int(h * scale))
        g = cv2.resize(g, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    mscn = _mscn_coefficients(g)
    feat = _agg_features(mscn)

    mu_nat = np.array([0.0, 0.5, 0.0, 3.0, 0.0, 0.2, 0.0, 0.2], dtype=np.float32)
    var_nat = np.array([0.2, 0.8, 0.5, 2.0, 0.3, 0.6, 0.3, 0.6], dtype=np.float32)

    d = (feat - mu_nat) / (np.sqrt(var_nat) + 1e-6)
    score = float(np.sqrt(np.sum(d * d)))
    if not np.isfinite(score):
        raise ValueError("niqe_score_not_finite")
    return score
