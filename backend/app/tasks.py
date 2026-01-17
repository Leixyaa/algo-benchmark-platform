from __future__ import annotations

import random
import time
from typing import Any, Dict

import numpy as np

from .celery_app import celery_app
from .store import make_redis, load_run, save_run

# 真实算法 + 指标（阶段E）
import cv2
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .vision.dehaze_dcp import dehaze_dcp


def _simulate_metrics() -> Dict[str, float]:
    psnr = round(random.uniform(20, 35), 3)
    ssim = round(random.uniform(0.70, 0.98), 4)
    niqe = round(random.uniform(2.5, 6.5), 3)
    return {"PSNR": psnr, "SSIM": ssim, "NIQE": niqe}


def _niqe_gray_u8(img_gray_u8: np.ndarray) -> float:
    """
    尝试用 scikit-video 计算 NIQE。
    注意：skvideo.measure.niqe 只允许单通道输入。
    失败时抛异常，上层负责 fallback。
    """
    import skvideo.measure  # 延迟 import，避免没装时 worker 直接挂

    # skvideo 支持输入 (M,N) / (M,N,1) / (T,M,N,1) 等；这里用 (M,N)
    x = img_gray_u8.astype(np.float32)
    score = skvideo.measure.niqe(x)
    # 返回可能是 ndarray 或标量
    if hasattr(score, "__len__"):
        score = float(np.mean(score))
    return float(score)


def _make_synthetic_dehaze_pair(h: int = 360, w: int = 640) -> tuple[np.ndarray, np.ndarray]:
    """
    生成一对（清晰GT, 有雾输入），用于没有真实数据集时也能跑出“真实指标”
    GT: 随机自然纹理 + 渐变
    Hazy: I = J * t + A * (1 - t)
    """
    # base texture
    base = np.random.rand(h, w, 3).astype(np.float32)
    grad = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    gt = 0.65 * base + 0.35 * grad
    gt = np.clip(gt, 0, 1)

    # depth-like transmission
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    t = 0.35 + 0.55 * (1 - y)  # top clearer, bottom hazier
    t = np.clip(t, 0.1, 0.95).astype(np.float32)

    A = np.array([0.9, 0.9, 0.9], dtype=np.float32)  # atmospheric light
    hazy = gt * t[:, :, None] + A[None, None, :] * (1 - t[:, :, None])
    hazy = np.clip(hazy, 0, 1)

    gt_u8 = (gt * 255.0 + 0.5).astype(np.uint8)
    hazy_u8 = (hazy * 255.0 + 0.5).astype(np.uint8)
    return gt_u8, hazy_u8


def _compute_psnr_ssim(gt_bgr_u8: np.ndarray, pred_bgr_u8: np.ndarray) -> tuple[float, float]:
    gt_rgb = cv2.cvtColor(gt_bgr_u8, cv2.COLOR_BGR2RGB)
    pr_rgb = cv2.cvtColor(pred_bgr_u8, cv2.COLOR_BGR2RGB)

    gt01 = gt_rgb.astype(np.float32) / 255.0
    pr01 = pr_rgb.astype(np.float32) / 255.0

    psnr = float(peak_signal_noise_ratio(gt01, pr01, data_range=1.0))
    ssim = float(structural_similarity(gt01, pr01, channel_axis=2, data_range=1.0))
    return psnr, ssim


@celery_app.task(name="runs.execute")
def execute_run(run_id: str) -> Dict[str, Any]:
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        return {"ok": False, "error": "run_not_found"}

    # 进入 running
    now = time.time()
    run["status"] = "running"
    run["started_at"] = now
    run["error"] = None
    save_run(r, run_id, run)

    task_type = (run.get("task_type") or "").lower()

    try:
        # ===================== 阶段E：真实去雾（dehaze） =====================
        if task_type == "dehaze":
            gt_u8, hazy_u8 = _make_synthetic_dehaze_pair()

            # 演示用：保证状态能被前端看到（至少 1.6 秒）
            min_demo_seconds = 1.6
            demo_start = time.time()

            # 真实算法：DCP 去雾
            t0 = time.time()
            pred_u8 = dehaze_dcp(hazy_u8, patch=15, omega=0.95, t0=0.1)
            algo_elapsed = time.time() - t0

            # 若算法太快，补足时间（不影响结果，只为演示状态变化）
            remain = min_demo_seconds - (time.time() - demo_start)
            if remain > 0:
                time.sleep(remain)

            # 真实指标：PSNR / SSIM
            psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)

            # 真实指标：NIQE（失败则回退模拟）
            pred_gray = cv2.cvtColor(pred_u8, cv2.COLOR_BGR2GRAY)
            try:
                niqe = _niqe_gray_u8(pred_gray)
                niqe_fallback = False
            except Exception:
                niqe = float(_simulate_metrics()["NIQE"])
                niqe_fallback = True

            finished = time.time()
            run["status"] = "done"
            run["finished_at"] = finished
            run["elapsed"] = round(finished - run["started_at"], 3)
            run["metrics"] = {
                "PSNR": round(psnr, 3),
                "SSIM": round(ssim, 4),
                "NIQE": round(float(niqe), 3),
            }
            # 把算法耗时与是否回退写进 params，便于你答辩解释
            params = run.get("params") or {}
            params["real_algo"] = "DCP"
            params["algo_elapsed"] = round(float(algo_elapsed), 3)
            params["niqe_fallback"] = bool(niqe_fallback)
            run["params"] = params

            save_run(r, run_id, run)
            return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

        # ===================== 其他任务：仍保留模拟（兜底） =====================
        sleep_s = random.uniform(1.2, 3.0)
        time.sleep(sleep_s)

        metrics = _simulate_metrics()
        finished = time.time()
        run["status"] = "done"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - run["started_at"], 3)
        run["metrics"] = metrics
        save_run(r, run_id, run)
        return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

    except Exception as e:
        finished = time.time()
        run["status"] = "failed"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - run["started_at"], 3)
        run["error"] = f"{type(e).__name__}: {e}"
        save_run(r, run_id, run)
        return {"ok": False, "run_id": run_id, "error": run["error"]}
