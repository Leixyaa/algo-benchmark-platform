# -*- coding: utf-8 -*-
# backend/app/vision/niqe_simple.py
"""
一个轻量 NIQE 实现：不依赖 skvideo / scipy.misc.imresize
说明：
- 这是工程可用的 no-reference 质量分数（越小越好）
- 用于毕设平台“真实指标接入”，不追求与某个库完全一致的数值，只追求可复现与趋势合理
"""

from __future__ import annotations

import numpy as np
import cv2


def _to_gray_f32(img_bgr_u8: np.ndarray) -> np.ndarray:
    if img_bgr_u8.ndim == 2:
        g = img_bgr_u8
    else:
        g = cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2GRAY)
    return g.astype(np.float32)


def _mscn_coefficients(img: np.ndarray, C: float = 1.0) -> np.ndarray:
    # Mean Subtracted Contrast Normalized coefficients (MSCN)
    mu = cv2.GaussianBlur(img, (7, 7), 7 / 6)
    mu_sq = mu * mu
    sigma = cv2.GaussianBlur(img * img, (7, 7), 7 / 6)
    sigma = np.sqrt(np.abs(sigma - mu_sq))
    return (img - mu) / (sigma + C)


def _agg_features(mscn: np.ndarray) -> np.ndarray:
    # 简化版特征：MSCN 的均值、方差、偏度、峰度 + 一些相邻乘积统计
    x = mscn.reshape(-1)
    x_mean = float(np.mean(x))
    x_var = float(np.var(x))

    # 偏度/峰度（避免引入 scipy.stats，自己算）
    eps = 1e-9
    x_std = np.sqrt(x_var) + eps
    skew = float(np.mean(((x - x_mean) / x_std) ** 3))
    kurt = float(np.mean(((x - x_mean) / x_std) ** 4))  # 未减 3（工程上够用）

    # 邻域乘积（横向、纵向）
    h_prod = (mscn[:, :-1] * mscn[:, 1:]).reshape(-1)
    v_prod = (mscn[:-1, :] * mscn[1:, :]).reshape(-1)
    hp_mean, hp_var = float(np.mean(h_prod)), float(np.var(h_prod))
    vp_mean, vp_var = float(np.mean(v_prod)), float(np.var(v_prod))

    return np.array([x_mean, x_var, skew, kurt, hp_mean, hp_var, vp_mean, vp_var], dtype=np.float32)


def niqe_score(img_bgr_u8: np.ndarray) -> float:
    """
    返回一个 NIQE 风格的质量分数（越小越好）。
    这里用“与自然图像统计”的距离近似：
    - 使用预设的自然统计均值/方差（简化版，固定常量）
    - 计算特征向量与自然统计的马氏距离近似（用对角协方差）
    """
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

    # 统一尺度：缩放到较稳定的尺寸，避免太小图不稳定
    h, w = g.shape[:2]
    target_min = 256
    if min(h, w) < target_min:
        scale = target_min / float(min(h, w))
        new_w = max(8, int(w * scale))
        new_h = max(8, int(h * scale))
        g = cv2.resize(g, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    mscn = _mscn_coefficients(g)
    feat = _agg_features(mscn)

    # 经验自然统计（固定常量）：工程上用于“趋势合理/可复现”
    mu_nat = np.array([0.0, 0.5, 0.0, 3.0, 0.0, 0.2, 0.0, 0.2], dtype=np.float32)
    var_nat = np.array([0.2, 0.8, 0.5, 2.0, 0.3, 0.6, 0.3, 0.6], dtype=np.float32)

    # 对角协方差的马氏距离
    d = (feat - mu_nat) / (np.sqrt(var_nat) + 1e-6)
    score = float(np.sqrt(np.sum(d * d)))
    if not np.isfinite(score):
        raise ValueError("niqe_score_not_finite")
    return score
