# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import time
import os
import socket
import platform
import tracemalloc
from typing import Any, Dict

import numpy as np
import hashlib

from .celery_app import celery_app
from .store import make_redis, load_run, save_run, load_dataset, load_algorithm
from . import errors as err
from .selector import online_update_model_with_run

import cv2
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .vision.dehaze_dcp import dehaze_dcp
from .vision.niqe_simple import niqe_score


class RunCanceled(Exception):
    pass


class RunFailed(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = str(code or err.E_INTERNAL)
        self.message = str(message or "")
        self.detail = detail if isinstance(detail, dict) else None


def _stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _simulate_metrics(seed: int) -> Dict[str, float]:
    rng = random.Random(seed)
    psnr = round(rng.uniform(20, 35), 3)
    ssim = round(rng.uniform(0.70, 0.98), 4)
    niqe = round(rng.uniform(2.5, 6.5), 3)
    return {"PSNR": psnr, "SSIM": ssim, "NIQE": niqe}


ALLOWED_METRICS = ("PSNR", "SSIM", "NIQE")


def _normalize_selected_metrics(params: dict[str, Any] | None) -> list[str]:
    src = params if isinstance(params, dict) else {}
    raw = src.get("metrics")
    if not isinstance(raw, list):
        return list(ALLOWED_METRICS)
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip().upper()
        if name in ALLOWED_METRICS and name not in out:
            out.append(name)
    return out or list(ALLOWED_METRICS)


def _filter_metrics(metrics: dict[str, float], selected_metrics: list[str]) -> dict[str, float]:
    wanted = set(selected_metrics or ALLOWED_METRICS)
    return {k: v for k, v in metrics.items() if k in wanted}


def _filter_sample_metrics(sample: dict[str, Any], selected_metrics: list[str]) -> dict[str, Any]:
    wanted = set(selected_metrics or ALLOWED_METRICS)
    return {k: v for k, v in sample.items() if k == "name" or k in wanted}



def _make_synthetic_dehaze_pair(h: int = 360, w: int = 640) -> tuple[np.ndarray, np.ndarray]:
    """
    构造一组可复现的合成去雾样本，用于无真实配对数据时的演示兜底。
    GT 表示清晰图像，Hazy 按大气散射模型 I = J * t + A * (1 - t) 生成。
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
    将 GT 尺寸对齐到预测结果，避免因分辨率不一致导致指标计算失败。
    """
    if gt_bgr_u8.shape[:2] == pred_bgr_u8.shape[:2]:
        return gt_bgr_u8, pred_bgr_u8

    h, w = pred_bgr_u8.shape[:2]
    gt_resized = cv2.resize(gt_bgr_u8, (w, h), interpolation=cv2.INTER_AREA)
    return gt_resized, pred_bgr_u8


def _read_first_frame(video_path: str) -> np.ndarray | None:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    return frame


def _apply_gamma_bgr(img_bgr_u8: np.ndarray, gamma: float) -> np.ndarray:
    g = max(0.05, float(gamma))
    x = img_bgr_u8.astype(np.float32) / 255.0
    y = np.clip(np.power(x, g), 0.0, 1.0)
    return (y * 255.0 + 0.5).astype(np.uint8)


def _apply_clahe_bgr(img_bgr_u8: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    lab = cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=tile_grid_size)
    l2 = clahe.apply(l)
    out = cv2.merge([l2, a, b])
    return cv2.cvtColor(out, cv2.COLOR_LAB2BGR)


def _unsharp_mask(img_bgr_u8: np.ndarray, sigma: float = 1.0, amount: float = 1.6) -> np.ndarray:
    blur = cv2.GaussianBlur(img_bgr_u8, (0, 0), sigmaX=float(sigma))
    return cv2.addWeighted(img_bgr_u8, float(amount), blur, -float(amount - 1.0), 0)


def _laplacian_sharpen(img_bgr_u8: np.ndarray, strength: float = 0.8) -> np.ndarray:
    g = cv2.cvtColor(img_bgr_u8, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(g, ddepth=cv2.CV_32F, ksize=3)
    lap = cv2.convertScaleAbs(lap)
    lap_bgr = cv2.cvtColor(lap, cv2.COLOR_GRAY2BGR)
    return cv2.addWeighted(img_bgr_u8, 1.0, lap_bgr, float(strength), 0)


def _get_num(params: dict[str, Any], key: str, default: float, min_v: float | None = None, max_v: float | None = None) -> float:
    v = params.get(key, default)
    try:
        x = float(v)
    except Exception:
        x = float(default)
    if min_v is not None:
        x = max(float(min_v), x)
    if max_v is not None:
        x = min(float(max_v), x)
    return x


def _get_int(params: dict[str, Any], key: str, default: int, min_v: int | None = None, max_v: int | None = None) -> int:
    v = params.get(key, default)
    try:
        x = int(v)
    except Exception:
        x = int(default)
    if min_v is not None:
        x = max(int(min_v), x)
    if max_v is not None:
        x = min(int(max_v), x)
    return x


def _is_retryable_exception(e: Exception) -> bool:
    if isinstance(e, (TimeoutError, ConnectionError)):
        return True
    if isinstance(e, OSError):
        return True
    return False


def _make_runtime_resource(
    wall_start: float,
    cpu_start: float,
    attempt_count: int,
    max_attempts: int,
    retry_count: int,
) -> dict[str, Any]:
    wall_s = max(0.0, time.time() - wall_start)
    cpu_s = max(0.0, time.process_time() - cpu_start)
    current_b = 0
    peak_b = 0
    if tracemalloc.is_tracing():
        current_b, peak_b = tracemalloc.get_traced_memory()
    return {
        "wall_s": round(float(wall_s), 6),
        "cpu_s": round(float(cpu_s), 6),
        "cpu_ratio": round(float(cpu_s / wall_s), 6) if wall_s > 0 else 0.0,
        "python_mem_current_mb": round(float(current_b) / 1024.0 / 1024.0, 3),
        "python_mem_peak_mb": round(float(peak_b) / 1024.0 / 1024.0, 3),
        "attempt_count": int(attempt_count),
        "max_attempts": int(max_attempts),
        "retry_count": int(retry_count),
    }


def _attach_runtime_to_run(
    run: dict[str, Any],
    wall_start: float,
    cpu_start: float,
    attempt_count: int,
    max_attempts: int,
    retry_count: int,
) -> None:
    record = run.get("record") if isinstance(run.get("record"), dict) else {}
    record["runtime_resource"] = _make_runtime_resource(
        wall_start=wall_start,
        cpu_start=cpu_start,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        retry_count=retry_count,
    )
    run["record"] = record


def _compute_run_for_task_from_pairs(
    pairs: list[Any],
    compute_pred,
    min_demo_seconds: float,
    demo_start: float,
    seed: int,
    check_cancel,
    strict_validate: bool,
    selected_metrics: list[str],
) -> tuple[dict[str, float], dict[str, Any], list[dict[str, Any]]]:
    psnr_list: list[float] = []
    ssim_list: list[float] = []
    niqe_list: list[float] = []
    algo_elapsed_list: list[float] = []
    metric_elapsed_list: list[float] = []
    metric_psnr_ssim_elapsed_list: list[float] = []
    metric_niqe_elapsed_list: list[float] = []
    samples: list[dict[str, Any]] = []
    read_ok = 0
    read_fail = 0
    processed_count = 0
    need_psnr_ssim = "PSNR" in selected_metrics or "SSIM" in selected_metrics
    need_niqe = "NIQE" in selected_metrics

    for pair in pairs:
        check_cancel()
        inp_u8 = cv2.imread(str(pair.input_path), cv2.IMREAD_COLOR)
        gt_u8 = cv2.imread(str(pair.gt_path), cv2.IMREAD_COLOR)
        if inp_u8 is None or gt_u8 is None:
            read_fail += 1
            continue
        read_ok += 1

        t0 = time.time()
        pred_u8 = compute_pred(inp_u8, gt_u8, pair)
        algo_elapsed_list.append(time.time() - t0)
        processed_count += 1

        gt_u8, pred_u8 = _resize_to_match(gt_u8, pred_u8)
        m0 = time.time()
        sample = {"name": getattr(pair, "name", None) or ""}
        if need_psnr_ssim:
            psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)
            metric_psnr_ssim_elapsed_list.append(time.time() - m0)
            psnr_list.append(psnr)
            ssim_list.append(ssim)
            sample["PSNR"] = round(float(psnr), 3)
            sample["SSIM"] = round(float(ssim), 4)

        if need_niqe:
            m1 = time.time()
            niqe = float(niqe_score(pred_u8))
            metric_niqe_elapsed_list.append(time.time() - m1)
            niqe_list.append(float(niqe))
            sample["NIQE"] = round(float(niqe), 3)

        metric_elapsed_list.append(time.time() - m0)
        samples.append(_filter_sample_metrics(sample, selected_metrics))

    if processed_count <= 0:
        if strict_validate:
            raise RunFailed(
                err.E_READ_IMAGE_FAIL,
                "数据集样本读取失败，无法计算有效指标",
                {"pair_used": len(pairs), "read_ok": read_ok, "read_fail": read_fail},
            )
        remain = min_demo_seconds - (time.time() - demo_start)
        if remain > 0:
            time.sleep(remain)
        metrics = _filter_metrics(_simulate_metrics(seed), selected_metrics)
        params = {"data_mode": "dataset_read_failed_or_empty"}
        return metrics, params, samples

    algo_elapsed_mean = float(np.mean(algo_elapsed_list)) if algo_elapsed_list else 0.0
    algo_elapsed_sum = float(np.sum(algo_elapsed_list)) if algo_elapsed_list else 0.0
    metric_elapsed_mean = float(np.mean(metric_elapsed_list)) if metric_elapsed_list else 0.0
    metric_elapsed_sum = float(np.sum(metric_elapsed_list)) if metric_elapsed_list else 0.0
    metric_psnr_ssim_elapsed_mean = float(np.mean(metric_psnr_ssim_elapsed_list)) if metric_psnr_ssim_elapsed_list else 0.0
    metric_psnr_ssim_elapsed_sum = float(np.sum(metric_psnr_ssim_elapsed_list)) if metric_psnr_ssim_elapsed_list else 0.0
    metric_niqe_elapsed_mean = float(np.mean(metric_niqe_elapsed_list)) if metric_niqe_elapsed_list else 0.0
    metric_niqe_elapsed_sum = float(np.sum(metric_niqe_elapsed_list)) if metric_niqe_elapsed_list else 0.0

    remain = min_demo_seconds - (time.time() - demo_start)
    if remain > 0:
        time.sleep(remain)

    metrics: dict[str, float] = {}
    if psnr_list and "PSNR" in selected_metrics:
        metrics["PSNR"] = round(float(np.mean(psnr_list)), 3)
    if ssim_list and "SSIM" in selected_metrics:
        metrics["SSIM"] = round(float(np.mean(ssim_list)), 4)
    if niqe_list:
        metrics["NIQE"] = round(float(np.mean(niqe_list)), 3)
    params = {
        "data_mode": "real_dataset",
        "data_used": processed_count,
        "algo_elapsed_mean": round(float(algo_elapsed_mean), 6),
        "algo_elapsed_sum": round(float(algo_elapsed_sum), 6),
        "metric_elapsed_mean": round(float(metric_elapsed_mean), 6),
        "metric_elapsed_sum": round(float(metric_elapsed_sum), 6),
        "metric_psnr_ssim_elapsed_mean": round(float(metric_psnr_ssim_elapsed_mean), 6),
        "metric_psnr_ssim_elapsed_sum": round(float(metric_psnr_ssim_elapsed_sum), 6),
        "metric_niqe_elapsed_mean": round(float(metric_niqe_elapsed_mean), 6),
        "metric_niqe_elapsed_sum": round(float(metric_niqe_elapsed_sum), 6),
        "read_ok": read_ok,
        "read_fail": read_fail,
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
    cancel_key = f"run_cancel:{run_id}"
    run = load_run(r, run_id)
    if not run:
        return {"ok": False, "error": "run_not_found"}
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    wall_start = time.time()
    cpu_start = time.process_time()

    status0 = (run.get("status") or "").lower()
    p0 = run.get("params") if isinstance(run.get("params"), dict) else {}
    retry_max_attempts = _get_int(p0, "retry_max_attempts", 3, 1, 5)
    record0 = run.get("record") if isinstance(run.get("record"), dict) else {}
    retry0 = record0.get("retry") if isinstance(record0.get("retry"), dict) else {}
    prev_attempt = _get_int(retry0, "attempt_count", 0, 0, 100)
    attempt_count = prev_attempt + 1
    retry_count = max(0, attempt_count - 1)

    if status0 in {"canceled"} or run.get("cancel_requested"):
        finished = time.time()
        run["status"] = "canceled"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - (run.get("started_at") or run.get("created_at") or finished), 3)
        run["error"] = "任务已取消"
        run["error_code"] = err.E_CANCELED
        run["error_detail"] = None
        _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
        save_run(r, run_id, run)
        return {"ok": False, "run_id": run_id, "error": run["error"]}

    now = time.time()
    run["status"] = "running"
    run["started_at"] = now
    run["error"] = None
    run["error_code"] = None
    run["error_detail"] = None
    save_run(r, run_id, run)

    task_type = (run.get("task_type") or "").lower()
    seed = _stable_seed(f"{run_id}|{task_type}|{run.get('dataset_id','')}|{run.get('algorithm_id','')}")
    dataset_id = run.get("dataset_id") or ""
    algorithm_id = run.get("algorithm_id") or ""
    strict_validate = bool(run.get("strict_validate"))

    record = run.get("record") if isinstance(run.get("record"), dict) else {}
    if isinstance(p0, dict):
        batch_id = p0.get("batch_id")
        batch_name = p0.get("batch_name")
        param_scheme = p0.get("param_scheme")
        if batch_id or batch_name or param_scheme:
            record["batch"] = {
                "batch_id": batch_id,
                "batch_name": batch_name,
                "param_scheme": param_scheme,
            }
    record.update(
        {
            "task_type": task_type,
            "seed": seed,
            "strict_validate": strict_validate,
            "retry": {
                "attempt_count": attempt_count,
                "retry_count": retry_count,
                "max_attempts": retry_max_attempts,
            },
            "worker": {
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "python": platform.python_version(),
            },
        }
    )
    ds = load_dataset(r, dataset_id) if dataset_id else None
    if isinstance(ds, dict):
        record["dataset"] = {
            "dataset_id": dataset_id,
            "name": ds.get("name"),
            "type": ds.get("type"),
            "size": ds.get("size"),
            "meta": ds.get("meta") if isinstance(ds.get("meta"), dict) else {},
        }
    alg = load_algorithm(r, algorithm_id) if algorithm_id else None
    if isinstance(alg, dict):
        record["algorithm"] = {
            "algorithm_id": algorithm_id,
            "task": alg.get("task"),
            "name": alg.get("name"),
            "impl": alg.get("impl"),
            "version": alg.get("version"),
        }
    run["record"] = record
    save_run(r, run_id, run)

    try:
        def check_cancel():
            cur = load_run(r, run_id) or {}
            s = (cur.get("status") or "").lower()
            flag = r.get(cancel_key)
            if flag or cur.get("cancel_requested") or s in {"canceled", "canceling"}:
                raise RunCanceled()

        if task_type in {"dehaze", "denoise", "deblur", "sr", "lowlight", "video_denoise", "video_sr"}:
            from pathlib import Path
            from .vision.dataset_io import find_paired_images, find_paired_videos

            algorithm_id = (algorithm_id or "").lower()
            algo_params = run.get("params") if isinstance(run.get("params"), dict) else {}
            selected_metrics = _normalize_selected_metrics(algo_params)
            data_root = Path(__file__).resolve().parents[1] / "data"  # backend/app/.. -> backend/data

            min_demo_seconds = 1.6
            demo_start = time.time()

            input_dir_by_task = {
                "dehaze": "hazy",
                "denoise": "noisy",
                "deblur": "blur",
                "sr": "lr",
                "lowlight": "dark",
                "video_denoise": "noisy",
                "video_sr": "lr",
            }
            input_dirname = input_dir_by_task.get(task_type, "hazy")
            is_video_task = task_type.startswith("video_")
            # 获取数据集所有者
            owner_id = run.get("owner_id", "system")
            if is_video_task:
                pairs = find_paired_videos(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt", limit=5)
            else:
                pairs = find_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt", limit=5)
            try:
                from .vision.dataset_io import count_paired_images, count_paired_videos

                if is_video_task:
                    total_pairs = count_paired_videos(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt")
                else:
                    total_pairs = count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt")
            except Exception:
                total_pairs = None
            record = run.get("record") if isinstance(run.get("record"), dict) else {}
            record.update(
                {
                    "data_mode": "paired_videos" if (pairs and is_video_task) else ("paired_images" if pairs else "synthetic_no_dataset"),
                    "input_dir": input_dirname,
                    "pair_used": len(pairs) if pairs else 0,
                    "pair_total": total_pairs,
                }
            )
            run["record"] = record
            save_run(r, run_id, run)

            def pick_impl_name() -> str:
                if task_type == "dehaze":
                    if algorithm_id.startswith("alg_dehaze_clahe"):
                        return "CLAHE"
                    if algorithm_id.startswith("alg_dehaze_gamma"):
                        return "Gamma"
                    return "DCP"
                if task_type == "denoise":
                    if algorithm_id.startswith("alg_denoise_bilateral"):
                        return "Bilateral"
                    if algorithm_id.startswith("alg_denoise_gaussian"):
                        return "Gaussian"
                    if algorithm_id.startswith("alg_denoise_median"):
                        return "Median"
                    return "FastNLMeans"
                if task_type == "deblur":
                    if algorithm_id.startswith("alg_deblur_laplacian"):
                        return "LaplacianSharpen"
                    return "UnsharpMask"
                if task_type == "sr":
                    if algorithm_id == "alg_sr_nearest":
                        return "Nearest"
                    if algorithm_id == "alg_sr_linear":
                        return "Linear"
                    if algorithm_id.startswith("alg_sr_lanczos"):
                        return "Lanczos"
                    if algorithm_id.startswith("alg_sr_bicubic"):
                        return "Bicubic"
                    return "Bicubic"
                if task_type == "lowlight":
                    if algorithm_id.startswith("alg_lowlight_clahe"):
                        return "CLAHE"
                    if algorithm_id == "alg_lowlight_hybrid":
                        return "GammaCLAHEHybrid"
                    return "Gamma"
                if task_type == "video_denoise":
                    if algorithm_id.startswith("alg_video_denoise_median"):
                        return "VideoMedian"
                    return "VideoGaussian"
                if task_type == "video_sr":
                    if algorithm_id == "alg_video_sr_nearest":
                        return "VideoNearest"
                    if algorithm_id == "alg_video_sr_linear":
                        return "VideoLinear"
                    if algorithm_id.startswith("alg_video_sr_lanczos"):
                        return "VideoLanczos"
                    if algorithm_id.startswith("alg_video_sr_bicubic"):
                        return "VideoBicubic"
                    return "VideoBicubic"
                return "Baseline"

            def compute_pred(inp_u8: np.ndarray, gt_u8: np.ndarray, pair: Any) -> np.ndarray:
                if task_type == "dehaze":
                    if algorithm_id.startswith("alg_dehaze_clahe"):
                        clip = _get_num(algo_params, "clahe_clip_limit", 2.0, 0.1, 40.0)
                        return _apply_clahe_bgr(inp_u8, clip_limit=clip)
                    if algorithm_id.startswith("alg_dehaze_gamma"):
                        gamma = _get_num(algo_params, "gamma", 0.75, 0.05, 5.0)
                        return _apply_gamma_bgr(inp_u8, gamma=gamma)
                    patch = _get_int(algo_params, "dcp_patch", 15, 3, 51)
                    omega = _get_num(algo_params, "dcp_omega", 0.95, 0.0, 1.5)
                    t0 = _get_num(algo_params, "dcp_t0", 0.1, 0.01, 0.5)
                    return dehaze_dcp(inp_u8, patch=patch, omega=omega, t0=t0)
                if task_type == "denoise":
                    if algorithm_id.startswith("alg_denoise_bilateral"):
                        d = _get_int(algo_params, "bilateral_d", 7, 1, 25)
                        sc = _get_num(algo_params, "bilateral_sigmaColor", 35, 1, 200)
                        ss = _get_num(algo_params, "bilateral_sigmaSpace", 35, 1, 200)
                        return cv2.bilateralFilter(inp_u8, d=d, sigmaColor=sc, sigmaSpace=ss)
                    if algorithm_id.startswith("alg_denoise_gaussian"):
                        sigma = _get_num(algo_params, "gaussian_sigma", 1.0, 0.05, 20.0)
                        return cv2.GaussianBlur(inp_u8, (0, 0), sigmaX=sigma)
                    if algorithm_id.startswith("alg_denoise_median"):
                        k = _get_int(algo_params, "median_ksize", 3, 1, 31)
                        if k % 2 == 0:
                            k += 1
                        return cv2.medianBlur(inp_u8, k)
                    h = _get_num(algo_params, "nlm_h", 10, 1, 50)
                    hc = _get_num(algo_params, "nlm_hColor", 10, 1, 50)
                    tw = _get_int(algo_params, "nlm_templateWindowSize", 7, 3, 21)
                    sw = _get_int(algo_params, "nlm_searchWindowSize", 21, 3, 51)
                    if tw % 2 == 0:
                        tw += 1
                    if sw % 2 == 0:
                        sw += 1
                    return cv2.fastNlMeansDenoisingColored(inp_u8, None, h, hc, tw, sw)
                if task_type == "deblur":
                    if algorithm_id.startswith("alg_deblur_laplacian"):
                        st = _get_num(algo_params, "laplacian_strength", 0.7, 0.0, 5.0)
                        return _laplacian_sharpen(inp_u8, strength=st)
                    sigma = _get_num(algo_params, "unsharp_sigma", 1.0, 0.05, 10.0)
                    amount = _get_num(algo_params, "unsharp_amount", 1.6, 1.0, 5.0)
                    return _unsharp_mask(inp_u8, sigma=sigma, amount=amount)
                if task_type == "sr":
                    h, w = gt_u8.shape[:2]
                    if algorithm_id == "alg_sr_nearest":
                        return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_NEAREST)
                    if algorithm_id == "alg_sr_linear":
                        return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_LINEAR)
                    if algorithm_id.startswith("alg_sr_lanczos"):
                        pred = cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_LANCZOS4)
                        if algorithm_id.endswith("_sharp"):
                            sigma = _get_num(algo_params, "unsharp_sigma", 0.8, 0.05, 10.0)
                            amount = _get_num(algo_params, "unsharp_amount", 1.2, 1.0, 5.0)
                            return _unsharp_mask(pred, sigma=sigma, amount=amount)
                        return pred
                    if algorithm_id.startswith("alg_sr_bicubic"):
                        pred = cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_CUBIC)
                        if algorithm_id.endswith("_sharp"):
                            sigma = _get_num(algo_params, "unsharp_sigma", 0.8, 0.05, 10.0)
                            amount = _get_num(algo_params, "unsharp_amount", 1.3, 1.0, 5.0)
                            return _unsharp_mask(pred, sigma=sigma, amount=amount)
                        return pred
                    return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_CUBIC)
                if task_type == "lowlight":
                    if algorithm_id.startswith("alg_lowlight_clahe"):
                        clip = _get_num(algo_params, "clahe_clip_limit", 2.5, 0.1, 40.0)
                        return _apply_clahe_bgr(inp_u8, clip_limit=clip)
                    if algorithm_id == "alg_lowlight_hybrid":
                        gamma = _get_num(algo_params, "lowlight_gamma", 0.62, 0.05, 5.0)
                        clip = _get_num(algo_params, "clahe_clip_limit", 2.6, 0.1, 40.0)
                        return _apply_clahe_bgr(_apply_gamma_bgr(inp_u8, gamma=gamma), clip_limit=clip)
                    gamma = _get_num(algo_params, "lowlight_gamma", 0.6, 0.05, 5.0)
                    return _apply_gamma_bgr(inp_u8, gamma=gamma)
                if task_type == "video_denoise":
                    if algorithm_id.startswith("alg_video_denoise_median"):
                        k = _get_int(algo_params, "median_ksize", 3, 1, 31)
                        if k % 2 == 0:
                            k += 1
                        return cv2.medianBlur(inp_u8, k)
                    sigma = _get_num(algo_params, "gaussian_sigma", 1.0, 0.05, 20.0)
                    return cv2.GaussianBlur(inp_u8, (0, 0), sigmaX=sigma)
                if task_type == "video_sr":
                    h, w = gt_u8.shape[:2]
                    if algorithm_id == "alg_video_sr_nearest":
                        return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_NEAREST)
                    if algorithm_id == "alg_video_sr_linear":
                        return cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_LINEAR)
                    if algorithm_id.startswith("alg_video_sr_lanczos"):
                        pred = cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_LANCZOS4)
                        if algorithm_id.endswith("_sharp"):
                            sigma = _get_num(algo_params, "unsharp_sigma", 0.8, 0.05, 10.0)
                            amount = _get_num(algo_params, "unsharp_amount", 1.2, 1.0, 5.0)
                            return _unsharp_mask(pred, sigma=sigma, amount=amount)
                        return pred
                    pred = cv2.resize(inp_u8, (w, h), interpolation=cv2.INTER_CUBIC)
                    if algorithm_id.startswith("alg_video_sr_bicubic") and algorithm_id.endswith("_sharp"):
                        sigma = _get_num(algo_params, "unsharp_sigma", 0.8, 0.05, 10.0)
                        amount = _get_num(algo_params, "unsharp_amount", 1.3, 1.0, 5.0)
                        return _unsharp_mask(pred, sigma=sigma, amount=amount)
                    return pred
                return inp_u8

            if pairs:
                if is_video_task:
                    psnr_list: list[float] = []
                    ssim_list: list[float] = []
                    niqe_list: list[float] = []
                    samples: list[dict[str, Any]] = []
                    read_ok = 0
                    read_fail = 0
                    for pair in pairs:
                        check_cancel()
                        inp_u8 = _read_first_frame(str(pair.input_path))
                        gt_u8 = _read_first_frame(str(pair.gt_path))
                        if inp_u8 is None or gt_u8 is None:
                            read_fail += 1
                            continue
                        read_ok += 1
                        pred_u8 = compute_pred(inp_u8, gt_u8, pair)
                        gt_u8, pred_u8 = _resize_to_match(gt_u8, pred_u8)
                        sample = {"name": getattr(pair, "name", None) or ""}
                        if "PSNR" in selected_metrics or "SSIM" in selected_metrics:
                            psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)
                            psnr_list.append(float(psnr))
                            ssim_list.append(float(ssim))
                            sample["PSNR"] = round(float(psnr), 3)
                            sample["SSIM"] = round(float(ssim), 4)
                        if "NIQE" in selected_metrics:
                            niqe = float(niqe_score(pred_u8))
                            niqe_list.append(float(niqe))
                            sample["NIQE"] = round(float(niqe), 3)
                        samples.append(_filter_sample_metrics(sample, selected_metrics))
                    if read_ok <= 0:
                        if strict_validate:
                            raise RunFailed(err.E_READ_IMAGE_FAIL, "video_read_failed_or_empty", {"pair_used": len(pairs), "read_ok": read_ok, "read_fail": read_fail})
                        metrics = _filter_metrics(_simulate_metrics(seed), selected_metrics)
                        params_patch = {"data_mode": "dataset_read_failed_or_empty"}
                    else:
                        metrics = {}
                        if psnr_list and "PSNR" in selected_metrics:
                            metrics["PSNR"] = round(float(np.mean(psnr_list)), 3)
                        if ssim_list and "SSIM" in selected_metrics:
                            metrics["SSIM"] = round(float(np.mean(ssim_list)), 4)
                        if niqe_list:
                            metrics["NIQE"] = round(float(np.mean(niqe_list)), 3)
                        params_patch = {"data_mode": "real_dataset", "data_used": read_ok, "read_ok": read_ok, "read_fail": read_fail}
                else:
                    metrics, params_patch, samples = _compute_run_for_task_from_pairs(
                        pairs=pairs,
                        compute_pred=compute_pred,
                        min_demo_seconds=min_demo_seconds,
                        demo_start=demo_start,
                        seed=seed,
                        check_cancel=check_cancel,
                        strict_validate=strict_validate,
                        selected_metrics=selected_metrics,
                    )
                finished = time.time()
                run["status"] = "done"
                run["finished_at"] = finished
                run["elapsed"] = round(finished - run["started_at"], 3)
                run["metrics"] = metrics
                run["error"] = None
                run["error_code"] = None
                run["error_detail"] = None
                params = run.get("params") or {}
                params.update(params_patch)
                params["real_algo"] = pick_impl_name()
                params["input_dir"] = input_dirname
                run["params"] = params
                run["samples"] = samples
                record = run.get("record") if isinstance(run.get("record"), dict) else {}
                record["data_mode"] = "paired_videos" if is_video_task else "paired_images"
                record["pair_used"] = len(pairs)
                record["timing"] = {
                    "algo_elapsed_mean": params.get("algo_elapsed_mean"),
                    "algo_elapsed_sum": params.get("algo_elapsed_sum"),
                    "metric_elapsed_mean": params.get("metric_elapsed_mean"),
                    "metric_elapsed_sum": params.get("metric_elapsed_sum"),
                    "metric_psnr_ssim_elapsed_mean": params.get("metric_psnr_ssim_elapsed_mean"),
                    "metric_psnr_ssim_elapsed_sum": params.get("metric_psnr_ssim_elapsed_sum"),
                    "metric_niqe_elapsed_mean": params.get("metric_niqe_elapsed_mean"),
                    "metric_niqe_elapsed_sum": params.get("metric_niqe_elapsed_sum"),
                    "read_ok": params.get("read_ok"),
                    "read_fail": params.get("read_fail"),
                    "data_used": params.get("data_used"),
                }
                run["record"] = record
                _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
                check_cancel()
                online_update_model_with_run(r, run)
                save_run(r, run_id, run)
                check_cancel()
                return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

            if strict_validate:
                raise RunFailed(
                    err.E_DATASET_NO_PAIR,
                    "数据集当前任务无可用配对，请检查 gt 与输入目录是否同名对应",
                    {"task_type": task_type, "dataset_id": dataset_id, "expected_input_dir": input_dirname},
                )

            check_cancel()
            gt_u8, inp_u8 = _make_synthetic_pair_for_task(task_type=task_type, seed=seed)
            t0 = time.time()
            pred_u8 = compute_pred(inp_u8, gt_u8, None)
            algo_elapsed = time.time() - t0
            gt_u8, pred_u8 = _resize_to_match(gt_u8, pred_u8)
            m0 = time.time()
            metrics = {}
            sample = {"name": "synthetic"}
            m_psnr_ssim = 0.0
            m_niqe = 0.0
            if "PSNR" in selected_metrics or "SSIM" in selected_metrics:
                psnr, ssim = _compute_psnr_ssim(gt_u8, pred_u8)
                m_psnr_ssim = time.time() - m0
                if "PSNR" in selected_metrics:
                    metrics["PSNR"] = round(float(psnr), 3)
                if "SSIM" in selected_metrics:
                    metrics["SSIM"] = round(float(ssim), 4)
                sample["PSNR"] = round(float(psnr), 3)
                sample["SSIM"] = round(float(ssim), 4)
            if "NIQE" in selected_metrics:
                m1 = time.time()
                niqe = float(niqe_score(pred_u8))
                m_niqe = time.time() - m1
                metrics["NIQE"] = round(float(niqe), 3)
                sample["NIQE"] = round(float(niqe), 3)
            metric_elapsed = time.time() - m0

            remain = min_demo_seconds - (time.time() - demo_start)
            if remain > 0:
                time.sleep(remain)

            check_cancel()
            finished = time.time()
            run["status"] = "done"
            run["finished_at"] = finished
            run["elapsed"] = round(finished - run["started_at"], 3)
            run["metrics"] = metrics
            run["error"] = None
            run["error_code"] = None
            run["error_detail"] = None
            params = run.get("params") or {}
            params["data_mode"] = "synthetic_no_dataset"
            params["algo_elapsed"] = round(float(algo_elapsed), 6)
            params["algo_elapsed_mean"] = round(float(algo_elapsed), 6)
            params["algo_elapsed_sum"] = round(float(algo_elapsed), 6)
            params["metric_elapsed_mean"] = round(float(metric_elapsed), 6)
            params["metric_elapsed_sum"] = round(float(metric_elapsed), 6)
            params["metric_psnr_ssim_elapsed_mean"] = round(float(m_psnr_ssim), 6)
            params["metric_psnr_ssim_elapsed_sum"] = round(float(m_psnr_ssim), 6)
            params["metric_niqe_elapsed_mean"] = round(float(m_niqe), 6)
            params["metric_niqe_elapsed_sum"] = round(float(m_niqe), 6)
            params["data_used"] = 1
            params["real_algo"] = pick_impl_name()
            params["input_dir"] = input_dirname
            run["params"] = params
            run["samples"] = [_filter_sample_metrics(sample, selected_metrics)]
            record = run.get("record") if isinstance(run.get("record"), dict) else {}
            record["data_mode"] = "synthetic_no_dataset"
            record["pair_used"] = 0
            record["timing"] = {
                "algo_elapsed_mean": params.get("algo_elapsed_mean"),
                "algo_elapsed_sum": params.get("algo_elapsed_sum"),
                "metric_elapsed_mean": params.get("metric_elapsed_mean"),
                "metric_elapsed_sum": params.get("metric_elapsed_sum"),
                "metric_psnr_ssim_elapsed_mean": params.get("metric_psnr_ssim_elapsed_mean"),
                "metric_psnr_ssim_elapsed_sum": params.get("metric_psnr_ssim_elapsed_sum"),
                "metric_niqe_elapsed_mean": params.get("metric_niqe_elapsed_mean"),
                "metric_niqe_elapsed_sum": params.get("metric_niqe_elapsed_sum"),
                "read_ok": None,
                "read_fail": None,
                "data_used": params.get("data_used"),
            }
            run["record"] = record
            _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
            check_cancel()
            online_update_model_with_run(r, run)
            save_run(r, run_id, run)
            check_cancel()
            return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

        check_cancel()
        sleep_s = random.uniform(1.2, 3.0)
        time.sleep(sleep_s)

        metrics = _filter_metrics(_simulate_metrics(seed), selected_metrics)
        finished = time.time()
        run["status"] = "done"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - run["started_at"], 3)
        run["metrics"] = metrics
        run["error"] = None
        run["error_code"] = None
        run["error_detail"] = None
        _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
        check_cancel()
        online_update_model_with_run(r, run)
        save_run(r, run_id, run)
        check_cancel()
        return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}

    except RunCanceled:
        finished = time.time()
        run["status"] = "canceled"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - (run.get("started_at") or finished), 3)
        run["error"] = "任务已取消"
        run["error_code"] = err.E_CANCELED
        run["error_detail"] = None
        _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
        save_run(r, run_id, run)
        r.delete(cancel_key)
        return {"ok": False, "run_id": run_id, "error": run["error"]}

    except RunFailed as e:
        finished = time.time()
        run["status"] = "failed"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - (run.get("started_at") or finished), 3)
        run["error"] = e.message
        run["error_code"] = e.code
        run["error_detail"] = e.detail
        record = run.get("record") if isinstance(run.get("record"), dict) else {}
        retry_info = record.get("retry") if isinstance(record.get("retry"), dict) else {}
        retry_info.update(
            {
                "attempt_count": attempt_count,
                "retry_count": retry_count,
                "max_attempts": retry_max_attempts,
                "will_retry": False,
            }
        )
        record["retry"] = retry_info
        run["record"] = record
        _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
        save_run(r, run_id, run)
        r.delete(cancel_key)
        return {"ok": False, "run_id": run_id, "error": run["error"], "error_code": run["error_code"]}

    except Exception as e:
        retryable = _is_retryable_exception(e)
        can_retry = retryable and attempt_count < retry_max_attempts
        if can_retry:
            backoff_s = min(8.0, 0.8 * (2 ** max(0, retry_count)))
            record = run.get("record") if isinstance(run.get("record"), dict) else {}
            retry_info = record.get("retry") if isinstance(record.get("retry"), dict) else {}
            retry_info.update(
                {
                    "attempt_count": attempt_count,
                    "retry_count": retry_count,
                    "max_attempts": retry_max_attempts,
                    "will_retry": True,
                    "next_attempt": attempt_count + 1,
                    "backoff_s": round(float(backoff_s), 3),
                    "last_error_type": type(e).__name__,
                    "last_error_message": str(e),
                }
            )
            record["retry"] = retry_info
            run["record"] = record
            run["status"] = "queued"
            run["started_at"] = None
            run["finished_at"] = None
            run["elapsed"] = None
            run["error"] = None
            run["error_code"] = None
            run["error_detail"] = None
            _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
            save_run(r, run_id, run)
            execute_run.apply_async((run_id,), countdown=float(backoff_s))
            return {"ok": False, "run_id": run_id, "retrying": True, "next_attempt": attempt_count + 1}
        finished = time.time()
        run["status"] = "failed"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - run["started_at"], 3)
        run["error"] = f"{type(e).__name__}: {e}"
        run["error_code"] = err.E_RETRY_EXHAUSTED if retryable else err.E_INTERNAL
        run["error_detail"] = {
            "type": type(e).__name__,
            "retryable": bool(retryable),
            "attempt_count": attempt_count,
            "retry_count": retry_count,
            "max_attempts": retry_max_attempts,
        }
        record = run.get("record") if isinstance(run.get("record"), dict) else {}
        retry_info = record.get("retry") if isinstance(record.get("retry"), dict) else {}
        retry_info.update(
            {
                "attempt_count": attempt_count,
                "retry_count": retry_count,
                "max_attempts": retry_max_attempts,
                "will_retry": False,
                "last_error_type": type(e).__name__,
                "last_error_message": str(e),
            }
        )
        record["retry"] = retry_info
        run["record"] = record
        _attach_runtime_to_run(run, wall_start, cpu_start, attempt_count, retry_max_attempts, retry_count)
        save_run(r, run_id, run)
        r.delete(cancel_key)
        return {"ok": False, "run_id": run_id, "error": run["error"]}
