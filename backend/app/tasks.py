# -*- coding: gbk -*-
from __future__ import annotations

import random
import time
from typing import Any, Dict

import numpy as np
import hashlib

from .celery_app import celery_app
from .store import make_redis, load_run, save_run

# 真实算法 + 指标（阶段E）
import cv2
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .vision.dehaze_dcp import dehaze_dcp
from .vision.niqe_simple import niqe_score


def _stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _simulate_metrics(seed: int) -> Dict[str, float]:
    rng = random.Random(seed)
    psnr = round(rng.uniform(20, 35), 3)
    ssim = round(rng.uniform(0.70, 0.98), 4)
    niqe = round(rng.uniform(2.5, 6.5), 3)
    return {"PSNR": psnr, "SSIM": ssim, "NIQE": niqe}



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

def _resize_to_match(gt_bgr_u8: np.ndarray, pred_bgr_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    保证两张图尺寸一致再算指标。
    默认把 gt resize 到 pred 的尺寸（更合理：pred 是算法输出的实际尺寸）。
    """
    if gt_bgr_u8.shape[:2] == pred_bgr_u8.shape[:2]:
        return gt_bgr_u8, pred_bgr_u8

    h, w = pred_bgr_u8.shape[:2]
    gt_resized = cv2.resize(gt_bgr_u8, (w, h), interpolation=cv2.INTER_AREA)
    return gt_resized, pred_bgr_u8


def _compute_run_for_task_from_pairs(
    pairs: list[Any],
    compute_pred,
    min_demo_seconds: float,
    demo_start: float,
    seed: int,
) -> tuple[dict[str, float], dict[str, Any], list[dict[str, Any]]]:
    psnr_list: list[float] = []
    ssim_list: list[float] = []
    niqe_list: list[float] = []
    algo_elapsed_list: list[float] = []
    niqe_fallback_any = False
    samples: list[dict[str, Any]] = []

    for pair in pairs:
        inp_u8 = cv2.imread(str(pair.input_path), cv2.IMREAD_COLOR)
        gt_u8 = cv2.imread(str(pair.gt_path), cv2.IMREAD_COLOR)
        if inp_u8 is None or gt_u8 is None:
            continue

        t0 = time.time()
        pred_u8 = compute_pred(inp_u8, gt_u8, pair)
        algo_elapsed_list.append(time.time() - t0)

        gt_u8, pred_u8 = _resize_to_match(gt_u8, pred_u8)
        psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)
        psnr_list.append(psnr)
        ssim_list.append(ssim)

        try:
            niqe = float(niqe_score(pred_u8))
        except Exception:
            niqe = float(_simulate_metrics(seed)["NIQE"])
            niqe_fallback_any = True
        niqe_list.append(float(niqe))

        samples.append(
            {
                "name": getattr(pair, "name", None) or "",
                "PSNR": round(float(psnr), 3),
                "SSIM": round(float(ssim), 4),
                "NIQE": round(float(niqe), 3),
            }
        )

    if not psnr_list:
        remain = min_demo_seconds - (time.time() - demo_start)
        if remain > 0:
            time.sleep(remain)
        metrics = _simulate_metrics(seed)
        params = {"data_mode": "dataset_read_failed_or_empty", "niqe_fallback": True}
        return metrics, params, samples

    psnr_mean = float(np.mean(psnr_list))
    ssim_mean = float(np.mean(ssim_list))
    niqe_mean = float(np.mean(niqe_list))
    algo_elapsed = float(np.mean(algo_elapsed_list)) if algo_elapsed_list else 0.0

    remain = min_demo_seconds - (time.time() - demo_start)
    if remain > 0:
        time.sleep(remain)

    metrics = {
        "PSNR": round(psnr_mean, 3),
        "SSIM": round(ssim_mean, 4),
        "NIQE": round(niqe_mean, 3),
    }
    params = {
        "data_mode": "real_dataset",
        "data_used": len(psnr_list),
        "algo_elapsed": round(float(algo_elapsed), 3),
        "niqe_fallback": bool(niqe_fallback_any),
    }
    return metrics, params, samples


def _make_synthetic_pair_for_task(task_type: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    h, w = 360, 640
    gt = (rng.random((h, w, 3)) * 255.0).astype(np.uint8)

    if task_type == "denoise":
        noise = rng.normal(0, 18.0, size=gt.shape).astype(np.float32)
        inp = np.clip(gt.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return gt, inp

    if task_type == "deblur":
        inp = cv2.GaussianBlur(gt, (0, 0), sigmaX=2.0)
        return gt, inp

    if task_type == "sr":
        lr = cv2.resize(gt, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        return gt, lr

    if task_type == "lowlight":
        inp = np.clip(gt.astype(np.float32) * 0.25, 0, 255).astype(np.uint8)
        return gt, inp

    if task_type == "dehaze":
        gt_u8, hazy_u8 = _make_synthetic_dehaze_pair(h=h, w=w)
        return gt_u8, hazy_u8

    return gt, gt



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
    seed = _stable_seed(f"{run_id}|{task_type}|{run.get('dataset_id','')}|{run.get('algorithm_id','')}")

    try:
        if task_type in {"dehaze", "denoise", "deblur", "sr", "lowlight"}:
            from pathlib import Path
            from .vision.dataset_io import find_paired_images

            dataset_id = run.get("dataset_id") or ""
            data_root = Path(__file__).resolve().parents[1] / "data"  # backend/app/.. -> backend/data

            min_demo_seconds = 1.6
            demo_start = time.time()

            input_dir_by_task = {
                "dehaze": "hazy",
                "denoise": "noisy",
                "deblur": "blur",
                "sr": "lr",
                "lowlight": "dark",
            }
            input_dirname = input_dir_by_task.get(task_type, "hazy")
            pairs = find_paired_images(data_root=data_root, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt", limit=5)

            def compute_pred(inp_u8: np.ndarray, gt_u8: np.ndarray, pair: Any) -> np.ndarray:
                if task_type == "dehaze":
                    return dehaze_dcp(inp_u8, patch=15, omega=0.95, t0=0.1)
                if task_type == "denoise":
                    return cv2.fastNlMeansDenoisingColored(inp_u8, None, 10, 10, 7, 21)
                if task_type == "deblur":
                    blur = cv2.GaussianBlur(inp_u8, (0, 0), sigmaX=1.0)
                    return cv2.addWeighted(inp_u8, 1.6, blur, -0.6, 0)
                if task_type == "sr":
                    h, w = gt_u8.shape[:2]
                    return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_CUBIC)
                if task_type == "lowlight":
                    rgb = cv2.cvtColor(inp_u8, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                    gamma = 0.6
                    out = np.clip(np.power(rgb, gamma), 0, 1)
                    out_u8 = (out * 255.0 + 0.5).astype(np.uint8)
                    return cv2.cvtColor(out_u8, cv2.COLOR_RGB2BGR)
                return inp_u8

            if pairs:
                metrics, params_patch, samples = _compute_run_for_task_from_pairs(
                    pairs=pairs,
                    compute_pred=compute_pred,
                    min_demo_seconds=min_demo_seconds,
                    demo_start=demo_start,
                    seed=seed,
                )
                finished = time.time()
                run["status"] = "done"
                run["finished_at"] = finished
                run["elapsed"] = round(finished - run["started_at"], 3)
                run["metrics"] = metrics
                params = run.get("params") or {}
                params.update(params_patch)
                params["real_algo"] = {"dehaze": "DCP", "denoise": "FastNLMeans", "deblur": "UnsharpMask", "sr": "Bicubic", "lowlight": "Gamma"}[task_type]
                params["input_dir"] = input_dirname
                run["params"] = params
                run["samples"] = samples
                save_run(r, run_id, run)
                return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

            gt_u8, inp_u8 = _make_synthetic_pair_for_task(task_type=task_type, seed=seed)
            t0 = time.time()
            pred_u8 = compute_pred(inp_u8, gt_u8, None)
            algo_elapsed = time.time() - t0
            gt_u8, pred_u8 = _resize_to_match(gt_u8, pred_u8)
            psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)
            try:
                niqe = float(niqe_score(pred_u8))
                niqe_fallback = False
            except Exception:
                niqe = float(_simulate_metrics(seed)["NIQE"])
                niqe_fallback = True

            remain = min_demo_seconds - (time.time() - demo_start)
            if remain > 0:
                time.sleep(remain)

            finished = time.time()
            run["status"] = "done"
            run["finished_at"] = finished
            run["elapsed"] = round(finished - run["started_at"], 3)
            run["metrics"] = {"PSNR": round(float(psnr), 3), "SSIM": round(float(ssim), 4), "NIQE": round(float(niqe), 3)}
            params = run.get("params") or {}
            params["data_mode"] = "synthetic_no_dataset"
            params["algo_elapsed"] = round(float(algo_elapsed), 3)
            params["niqe_fallback"] = bool(niqe_fallback)
            params["real_algo"] = {"dehaze": "DCP", "denoise": "FastNLMeans", "deblur": "UnsharpMask", "sr": "Bicubic", "lowlight": "Gamma"}[task_type]
            params["input_dir"] = input_dirname
            run["params"] = params
            run["samples"] = [{"name": "synthetic", "PSNR": round(float(psnr), 3), "SSIM": round(float(ssim), 4), "NIQE": round(float(niqe), 3)}]
            save_run(r, run_id, run)
            return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

        sleep_s = random.uniform(1.2, 3.0)
        time.sleep(sleep_s)

        metrics = _simulate_metrics(seed)
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
