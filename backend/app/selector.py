# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt
from typing import Any
import json
import time

import numpy as np


TASK_TYPES = ["dehaze", "denoise", "deblur", "sr", "lowlight", "video_denoise", "video_sr"]
MODEL_VERSION = 1


@dataclass
class ArmStat:
    algorithm_id: str
    score: float
    expected_reward: float
    mean_reward: float
    uncertainty: float
    exploration_bonus: float
    cold_start_bonus: float
    reliability: float
    sample_count: int


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _safe_elapsed_s(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    s = s.rstrip("sS")
    try:
        return float(s)
    except Exception:
        return None


def _safe_ts(run: dict[str, Any]) -> float:
    for k in ("finished_at", "started_at", "created_at"):
        v = run.get(k)
        if isinstance(v, (int, float)) and float(v) > 0:
            return float(v)
    return 0.0


def reward_from_run(run: dict[str, Any]) -> float | None:
    metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
    psnr = metrics.get("PSNR")
    ssim = metrics.get("SSIM")
    niqe = metrics.get("NIQE")
    elapsed = run.get("elapsed")
    p = _clamp01(1.0 / (1.0 + exp(-(float(psnr) - 24.0) / 4.0))) if isinstance(psnr, (int, float)) else None
    s = _clamp01(float(ssim)) if isinstance(ssim, (int, float)) else None
    n = _clamp01(1.0 / (1.0 + max(float(niqe), 0.0) / 5.0)) if isinstance(niqe, (int, float)) else None
    t_sec = _safe_elapsed_s(elapsed)
    t = _clamp01(exp(-max(t_sec, 0.0) / 8.0)) if isinstance(t_sec, (int, float)) else None
    vals = [x for x in [p, s, n, t] if x is not None]
    if not vals:
        return None
    if p is None:
        p = float(np.mean(vals))
    if s is None:
        s = float(np.mean(vals))
    if n is None:
        n = float(np.mean(vals))
    if t is None:
        t = float(np.mean(vals))
    reward = 0.35 * p + 0.3 * s + 0.25 * n + 0.1 * t
    return round(float(_clamp01(reward)), 6)


def build_context_vector(task_type: str, dataset_meta: dict[str, Any] | None) -> np.ndarray:
    meta = dataset_meta if isinstance(dataset_meta, dict) else {}
    pairs_map = meta.get("pairs_by_task") if isinstance(meta.get("pairs_by_task"), dict) else {}
    counts = meta.get("counts_by_dir") if isinstance(meta.get("counts_by_dir"), dict) else {}
    pair_count = float(pairs_map.get(task_type) or 0.0)
    gt_count = float(counts.get("gt") or 0.0)
    noisy_count = float(counts.get("noisy") or 0.0)
    lr_count = float(counts.get("lr") or 0.0)
    dark_count = float(counts.get("dark") or 0.0)
    blur_count = float(counts.get("blur") or 0.0)
    hazy_count = float(counts.get("hazy") or 0.0)
    ratio = pair_count / gt_count if gt_count > 0 else 0.0
    task_one_hot = [1.0 if task_type == t else 0.0 for t in TASK_TYPES]
    feats = [
        1.0,
        log(pair_count + 1.0),
        log(gt_count + 1.0),
        ratio,
        log(noisy_count + 1.0),
        log(lr_count + 1.0),
        log(dark_count + 1.0),
        log(blur_count + 1.0),
        log(hazy_count + 1.0),
        1.0 if task_type.startswith("video_") else 0.0,
        *task_one_hot,
    ]
    return np.asarray(feats, dtype=np.float64)


def build_run_context_vector(run: dict[str, Any]) -> np.ndarray:
    record = run.get("record") if isinstance(run.get("record"), dict) else {}
    task_type = str(run.get("task_type") or "")
    pair_total = float(record.get("pair_total") or record.get("pair_used") or 0.0)
    pair_used = float(record.get("pair_used") or 0.0)
    ratio = pair_used / pair_total if pair_total > 0 else 0.0
    input_dir = str(record.get("input_dir") or "")
    feats = [
        1.0,
        log(pair_total + 1.0),
        log(pair_used + 1.0),
        ratio,
        1.0 if input_dir == "noisy" else 0.0,
        1.0 if input_dir == "lr" else 0.0,
        1.0 if input_dir == "dark" else 0.0,
        1.0 if input_dir == "blur" else 0.0,
        1.0 if input_dir == "hazy" else 0.0,
        1.0 if task_type.startswith("video_") else 0.0,
        *[1.0 if task_type == t else 0.0 for t in TASK_TYPES],
    ]
    return np.asarray(feats, dtype=np.float64)


@dataclass
class FastSelectConfig:
    alpha: float = 0.35
    lambda_reg: float = 1.0
    recency_half_life_hours: float = 72.0
    cold_start_bonus: float = 0.08
    low_support_penalty: float = 0.06
    min_support: int = 3


def fast_select_algorithms(
    *,
    task_type: str,
    candidate_algorithm_ids: list[str],
    historical_runs: list[dict[str, Any]],
    target_context: np.ndarray,
    config: FastSelectConfig | None = None,
) -> list[ArmStat]:
    cfg = config if isinstance(config, FastSelectConfig) else FastSelectConfig()
    d = int(target_context.shape[0])
    mats: dict[str, np.ndarray] = {aid: np.eye(d, dtype=np.float64) * float(cfg.lambda_reg) for aid in candidate_algorithm_ids}
    vecs: dict[str, np.ndarray] = {aid: np.zeros((d, 1), dtype=np.float64) for aid in candidate_algorithm_ids}
    cnts: dict[str, int] = {aid: 0 for aid in candidate_algorithm_ids}
    sums: dict[str, float] = {aid: 0.0 for aid in candidate_algorithm_ids}
    eff_n: dict[str, float] = {aid: 0.0 for aid in candidate_algorithm_ids}

    ts_pool = [_safe_ts(x) for x in historical_runs]
    now_ts = max([x for x in ts_pool if x > 0], default=0.0)
    half_life_h = max(float(cfg.recency_half_life_hours), 1.0)

    for run in historical_runs:
        if str(run.get("task_type") or "") != task_type:
            continue
        aid = str(run.get("algorithm_id") or "")
        if aid not in mats:
            continue
        if str(run.get("status") or "").lower() != "done":
            continue
        reward = reward_from_run(run)
        if reward is None:
            continue
        x = build_run_context_vector(run).reshape(-1, 1)
        if x.shape[0] != d:
            continue
        ts = _safe_ts(run)
        age_h = max((now_ts - ts) / 3600.0, 0.0) if now_ts > 0 and ts > 0 else 0.0
        w = 0.5 ** (age_h / half_life_h)
        mats[aid] = mats[aid] + float(w) * (x @ x.T)
        vecs[aid] = vecs[aid] + float(w * reward) * x
        cnts[aid] += 1
        sums[aid] += float(w * reward)
        eff_n[aid] += float(w)

    xt = target_context.reshape(-1, 1)
    out: list[ArmStat] = []
    for aid in candidate_algorithm_ids:
        A = mats[aid]
        b = vecs[aid]
        theta = np.linalg.solve(A, b)
        mean = float((theta.T @ xt).reshape(()))
        z = np.linalg.solve(A, xt)
        unc = float(sqrt(max(float((xt.T @ z).reshape(())), 0.0)))
        n = cnts[aid]
        n_eff = eff_n[aid]
        hist_mean = sums[aid] / n_eff if n_eff > 0 else 0.0
        expected = _clamp01(float(0.65 * mean + 0.35 * hist_mean))
        support = min(max(n_eff / max(float(cfg.min_support), 1.0), 0.0), 1.0)
        reliability = support
        exploration_scale = 0.25 + 0.75 * reliability
        exploration = float(cfg.alpha) * unc * exploration_scale
        cold_bonus = float(cfg.cold_start_bonus) / sqrt(max(n_eff, 0.0) + 1.0)
        penalty = float(cfg.low_support_penalty) * (1.0 - reliability)
        score = float(expected + exploration + cold_bonus - penalty)
        if n_eff < 0.5:
            score = min(score, 0.55 + cold_bonus)
        out.append(
            ArmStat(
                algorithm_id=aid,
                score=round(score, 6),
                expected_reward=round(expected, 6),
                mean_reward=round(hist_mean, 6),
                uncertainty=round(unc, 6),
                exploration_bonus=round(exploration, 6),
                cold_start_bonus=round(cold_bonus, 6),
                reliability=round(reliability, 6),
                sample_count=n,
            )
        )

    out.sort(key=lambda x: x.score, reverse=True)
    return out


def _model_key(task_type: str) -> str:
    return f"bandit:fast_select:{task_type}:v{MODEL_VERSION}"


def _ensure_arm_state(model: dict[str, Any], algorithm_id: str, d: int, lambda_reg: float) -> dict[str, Any]:
    arms = model["arms"]
    arm = arms.get(algorithm_id)
    if isinstance(arm, dict):
        return arm
    arm = {
        "A": (np.eye(d, dtype=np.float64) * float(lambda_reg)).tolist(),
        "b": np.zeros((d, 1), dtype=np.float64).tolist(),
        "sample_count": 0,
        "weighted_reward_sum": 0.0,
        "effective_n": 0.0,
        "last_ts": 0.0,
    }
    arms[algorithm_id] = arm
    return arm


def load_online_model(r: Any, task_type: str) -> dict[str, Any] | None:
    s = r.get(_model_key(task_type))
    if not s:
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if int(obj.get("version") or 0) != MODEL_VERSION:
        return None
    if str(obj.get("task_type") or "") != task_type:
        return None
    if not isinstance(obj.get("arms"), dict):
        return None
    d = int(obj.get("feature_dim") or 0)
    if d <= 0:
        return None
    return obj


def save_online_model(r: Any, task_type: str, model: dict[str, Any]) -> None:
    model["updated_at"] = float(time.time())
    model["version"] = MODEL_VERSION
    model["task_type"] = task_type
    r.set(_model_key(task_type), json.dumps(model, ensure_ascii=False))


def _decay_arm_state(arm: dict[str, Any], now_ts: float, half_life_h: float) -> tuple[np.ndarray, np.ndarray, float, float]:
    A = np.asarray(arm.get("A"), dtype=np.float64)
    b = np.asarray(arm.get("b"), dtype=np.float64)
    n_eff = float(arm.get("effective_n") or 0.0)
    wrs = float(arm.get("weighted_reward_sum") or 0.0)
    last_ts = float(arm.get("last_ts") or 0.0)
    if now_ts > 0 and last_ts > 0 and half_life_h > 0:
        age_h = max((now_ts - last_ts) / 3600.0, 0.0)
        decay = 0.5 ** (age_h / half_life_h)
        A = A * float(decay)
        b = b * float(decay)
        n_eff = n_eff * float(decay)
        wrs = wrs * float(decay)
    return A, b, n_eff, wrs


def online_update_model_with_run(r: Any, run: dict[str, Any], config: FastSelectConfig | None = None) -> bool:
    if str(run.get("status") or "").lower() != "done":
        return False
    task_type = str(run.get("task_type") or "").strip().lower()
    algorithm_id = str(run.get("algorithm_id") or "").strip()
    if not task_type or not algorithm_id:
        return False
    reward = reward_from_run(run)
    if reward is None:
        return False
    cfg = config if isinstance(config, FastSelectConfig) else FastSelectConfig()
    x = build_run_context_vector(run).reshape(-1, 1)
    d = int(x.shape[0])
    model = load_online_model(r, task_type)
    if not model:
        model = {
            "version": MODEL_VERSION,
            "task_type": task_type,
            "feature_dim": d,
            "updated_at": float(time.time()),
            "arms": {},
            "run_ids": [],
        }
    if int(model.get("feature_dim") or 0) != d:
        model = {
            "version": MODEL_VERSION,
            "task_type": task_type,
            "feature_dim": d,
            "updated_at": float(time.time()),
            "arms": {},
            "run_ids": [],
        }
    run_id = str(run.get("run_id") or "")
    seen = model.get("run_ids") if isinstance(model.get("run_ids"), list) else []
    if run_id and run_id in seen:
        return False
    arm = _ensure_arm_state(model, algorithm_id, d, cfg.lambda_reg)
    ts = _safe_ts(run)
    now_ts = ts if ts > 0 else float(time.time())
    A, b, n_eff, wrs = _decay_arm_state(arm, now_ts=now_ts, half_life_h=max(float(cfg.recency_half_life_hours), 1.0))
    A = A + x @ x.T
    b = b + float(reward) * x
    n_eff += 1.0
    wrs += float(reward)
    arm["A"] = A.tolist()
    arm["b"] = b.tolist()
    arm["sample_count"] = int(arm.get("sample_count") or 0) + 1
    arm["effective_n"] = float(n_eff)
    arm["weighted_reward_sum"] = float(wrs)
    arm["last_ts"] = float(now_ts)
    if run_id:
        seen.append(run_id)
        if len(seen) > 6000:
            seen = seen[-6000:]
    model["run_ids"] = seen
    save_online_model(r, task_type, model)
    return True


def bootstrap_online_model_from_runs(
    r: Any,
    *,
    task_type: str,
    historical_runs: list[dict[str, Any]],
    config: FastSelectConfig | None = None,
) -> dict[str, Any]:
    cfg = config if isinstance(config, FastSelectConfig) else FastSelectConfig()
    runs = [
        x
        for x in historical_runs
        if str(x.get("task_type") or "").strip().lower() == task_type and str(x.get("status") or "").lower() == "done"
    ]
    if not runs:
        model = {"version": MODEL_VERSION, "task_type": task_type, "feature_dim": 17, "updated_at": float(time.time()), "arms": {}, "run_ids": []}
        save_online_model(r, task_type, model)
        return model
    runs.sort(key=lambda x: _safe_ts(x))
    d = int(build_run_context_vector(runs[-1]).shape[0])
    model = {"version": MODEL_VERSION, "task_type": task_type, "feature_dim": d, "updated_at": float(time.time()), "arms": {}, "run_ids": []}
    key = _model_key(task_type)
    r.set(key, json.dumps(model, ensure_ascii=False))
    for run in runs:
        online_update_model_with_run(r, run, cfg)
    return load_online_model(r, task_type) or model


def fast_select_algorithms_online(
    *,
    task_type: str,
    candidate_algorithm_ids: list[str],
    target_context: np.ndarray,
    model: dict[str, Any],
    config: FastSelectConfig | None = None,
) -> list[ArmStat]:
    cfg = config if isinstance(config, FastSelectConfig) else FastSelectConfig()
    d = int(target_context.shape[0])
    if int(model.get("feature_dim") or 0) != d:
        return []
    xt = target_context.reshape(-1, 1)
    out: list[ArmStat] = []
    now_ts = float(time.time())
    arms = model.get("arms") if isinstance(model.get("arms"), dict) else {}
    for aid in candidate_algorithm_ids:
        arm = arms.get(aid) if isinstance(arms.get(aid), dict) else None
        if arm:
            A_raw, b_raw, n_eff, wrs = _decay_arm_state(arm, now_ts=now_ts, half_life_h=max(float(cfg.recency_half_life_hours), 1.0))
            try:
                theta = np.linalg.solve(A_raw, b_raw)
                z = np.linalg.solve(A_raw, xt)
                unc = float(sqrt(max(float((xt.T @ z).reshape(())), 0.0)))
                mean = float((theta.T @ xt).reshape(()))
            except Exception:
                unc = 1.0
                mean = 0.0
            n = int(arm.get("sample_count") or 0)
            hist_mean = wrs / n_eff if n_eff > 0 else 0.0
        else:
            unc = 1.0
            mean = 0.0
            n = 0
            n_eff = 0.0
            hist_mean = 0.0
        expected = _clamp01(float(0.65 * mean + 0.35 * hist_mean))
        support = min(max(n_eff / max(float(cfg.min_support), 1.0), 0.0), 1.0)
        reliability = support
        exploration_scale = 0.25 + 0.75 * reliability
        exploration = float(cfg.alpha) * unc * exploration_scale
        cold_bonus = float(cfg.cold_start_bonus) / sqrt(max(n_eff, 0.0) + 1.0)
        penalty = float(cfg.low_support_penalty) * (1.0 - reliability)
        score = float(expected + exploration + cold_bonus - penalty)
        if n_eff < 0.5:
            score = min(score, 0.55 + cold_bonus)
        out.append(
            ArmStat(
                algorithm_id=aid,
                score=round(score, 6),
                expected_reward=round(expected, 6),
                mean_reward=round(hist_mean, 6),
                uncertainty=round(unc, 6),
                exploration_bonus=round(exploration, 6),
                cold_start_bonus=round(cold_bonus, 6),
                reliability=round(reliability, 6),
                sample_count=n,
            )
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out
