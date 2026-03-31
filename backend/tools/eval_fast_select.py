# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any
import argparse

import numpy as np

from backend.app.selector import build_context_vector, fast_select_algorithms


@dataclass(frozen=True)
class Cfg:
    seed: int = 20260323
    episodes: int = 160
    warmup: int = 40
    top_k: int = 2
    alpha: float = 0.35


TASK_ALGS = {
    "denoise": ["alg_dn_cnn", "alg_denoise_gaussian", "alg_denoise_median", "alg_denoise_bilateral"],
    "dehaze": ["alg_dehaze_dcp", "alg_dehaze_clahe", "alg_dehaze_gamma"],
    "sr": ["alg_sr_bicubic", "alg_sr_lanczos", "alg_sr_nearest"],
    "video_sr": ["alg_video_sr_bicubic", "alg_video_sr_lanczos"],
}

ALG_BASE_COST = {
    "alg_dn_cnn": 1.2,
    "alg_denoise_gaussian": 0.7,
    "alg_denoise_median": 0.8,
    "alg_denoise_bilateral": 1.0,
    "alg_dehaze_dcp": 1.4,
    "alg_dehaze_clahe": 0.8,
    "alg_dehaze_gamma": 0.6,
    "alg_sr_bicubic": 0.9,
    "alg_sr_lanczos": 1.1,
    "alg_sr_nearest": 0.5,
    "alg_video_sr_bicubic": 1.8,
    "alg_video_sr_lanczos": 2.1,
}


def _make_meta(rng: np.random.Generator, task_type: str) -> dict[str, Any]:
    gt = int(rng.integers(20, 320))
    noisy = int(rng.integers(10, 320))
    lr = int(rng.integers(10, 320))
    dark = int(rng.integers(10, 320))
    blur = int(rng.integers(10, 320))
    hazy = int(rng.integers(10, 320))
    pair = int(rng.integers(max(5, gt // 5), max(6, gt)))
    if task_type in {"video_sr"}:
        lr = max(lr, pair)
    if task_type in {"denoise"}:
        noisy = max(noisy, pair)
    if task_type in {"dehaze"}:
        hazy = max(hazy, pair)
    return {
        "pairs_by_task": {task_type: pair},
        "counts_by_dir": {"gt": gt, "noisy": noisy, "lr": lr, "dark": dark, "blur": blur, "hazy": hazy},
        "supported_task_types": [task_type],
    }


def _reward_to_metrics(reward: float) -> dict[str, float]:
    r = float(np.clip(reward, 0.0, 1.0))
    psnr = 20.0 + 16.0 * r
    ssim = 0.5 + 0.49 * r
    niqe = 8.5 * (1.0 - r)
    return {"PSNR": round(psnr, 4), "SSIM": round(ssim, 4), "NIQE": round(niqe, 4)}


def _reward_from_true(theta: np.ndarray, x: np.ndarray, rng: np.random.Generator) -> float:
    z = float(theta @ x) + float(rng.normal(0, 0.16))
    p = 1.0 / (1.0 + exp(-z))
    return float(np.clip(p, 0.0, 1.0))


def _sample_runtime(alg_id: str, rng: np.random.Generator) -> float:
    base = ALG_BASE_COST.get(alg_id, 1.0)
    noise = float(rng.normal(0, 0.08))
    return float(max(0.25, base + noise))


def _eval_policy(
    *,
    task_type: str,
    alg_ids: list[str],
    x: np.ndarray,
    theta_by_alg: dict[str, np.ndarray],
    rng: np.random.Generator,
    policy: str,
    history: list[dict[str, Any]],
    cfg: Cfg,
) -> tuple[str, float, float, list[dict[str, Any]]]:
    truth_reward = {aid: _reward_from_true(theta_by_alg[aid], x, rng) for aid in alg_ids}
    truth_cost = {aid: _sample_runtime(aid, rng) for aid in alg_ids}
    if policy == "full":
        cand = list(alg_ids)
    elif policy == "random":
        k = min(cfg.top_k, len(alg_ids))
        cand = list(rng.choice(np.asarray(alg_ids), size=k, replace=False))
    elif policy == "fast":
        stats = fast_select_algorithms(
            task_type=task_type,
            candidate_algorithm_ids=alg_ids,
            historical_runs=history,
            target_context=x,
            alpha=cfg.alpha,
            lambda_reg=1.0,
        )
        cand = [s.algorithm_id for s in stats[: min(cfg.top_k, len(stats))]]
    elif policy == "static":
        means = {}
        for aid in alg_ids:
            vals = []
            for run in history:
                if str(run.get("task_type") or "") != task_type:
                    continue
                if str(run.get("algorithm_id") or "") != aid:
                    continue
                m = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
                if not m:
                    continue
                vals.append(float(m.get("SSIM") or 0.0))
            means[aid] = float(np.mean(vals)) if vals else 0.0
        cand = [x[0] for x in sorted(means.items(), key=lambda kv: kv[1], reverse=True)[: min(cfg.top_k, len(alg_ids))]]
    else:
        raise RuntimeError(f"unknown policy {policy}")
    best = max(cand, key=lambda aid: truth_reward[aid])
    sel_reward = float(truth_reward[best])
    sel_cost = float(sum(truth_cost[aid] for aid in cand))
    new_runs = []
    for aid in cand:
        rr = truth_reward[aid]
        rec = {
            "task_type": task_type,
            "algorithm_id": aid,
            "status": "done",
            "metrics": _reward_to_metrics(rr),
            "elapsed": round(float(truth_cost[aid]), 4),
            "record": {"pair_total": 100, "pair_used": 60, "input_dir": "lr" if "sr" in task_type else "noisy"},
        }
        new_runs.append(rec)
    return best, sel_reward, sel_cost, new_runs


def run(cfg: Cfg) -> dict[str, Any]:
    rng = np.random.default_rng(cfg.seed)
    probe_x = build_context_vector("denoise", _make_meta(rng, "denoise"))
    d = int(probe_x.shape[0])

    theta_by_alg: dict[str, np.ndarray] = {}
    for _, algs in TASK_ALGS.items():
        for aid in algs:
            if aid in theta_by_alg:
                continue
            theta_by_alg[aid] = rng.normal(0, 0.8, size=(d,))

    history: list[dict[str, Any]] = []
    for _ in range(cfg.warmup):
        task_type = str(rng.choice(np.asarray(list(TASK_ALGS.keys()))))
        alg_ids = TASK_ALGS[task_type]
        x = build_context_vector(task_type, _make_meta(rng, task_type))
        _, _, _, new_runs = _eval_policy(
            task_type=task_type,
            alg_ids=alg_ids,
            x=x,
            theta_by_alg=theta_by_alg,
            rng=rng,
            policy="full",
            history=history,
            cfg=cfg,
        )
        history.extend(new_runs)

    stat = {
        "full_cost": [],
        "fast_cost": [],
        "rand_cost": [],
        "static_cost": [],
        "fast_regret": [],
        "rand_regret": [],
        "static_regret": [],
        "fast_hit": 0,
        "rand_hit": 0,
        "static_hit": 0,
    }

    for _ in range(cfg.episodes):
        task_type = str(rng.choice(np.asarray(list(TASK_ALGS.keys()))))
        alg_ids = TASK_ALGS[task_type]
        x = build_context_vector(task_type, _make_meta(rng, task_type))

        full_best, full_reward, full_cost, full_runs = _eval_policy(
            task_type=task_type,
            alg_ids=alg_ids,
            x=x,
            theta_by_alg=theta_by_alg,
            rng=rng,
            policy="full",
            history=history,
            cfg=cfg,
        )
        fast_best, fast_reward, fast_cost, fast_runs = _eval_policy(
            task_type=task_type,
            alg_ids=alg_ids,
            x=x,
            theta_by_alg=theta_by_alg,
            rng=rng,
            policy="fast",
            history=history,
            cfg=cfg,
        )
        rand_best, rand_reward, rand_cost, rand_runs = _eval_policy(
            task_type=task_type,
            alg_ids=alg_ids,
            x=x,
            theta_by_alg=theta_by_alg,
            rng=rng,
            policy="random",
            history=history,
            cfg=cfg,
        )
        static_best, static_reward, static_cost, static_runs = _eval_policy(
            task_type=task_type,
            alg_ids=alg_ids,
            x=x,
            theta_by_alg=theta_by_alg,
            rng=rng,
            policy="static",
            history=history,
            cfg=cfg,
        )

        stat["full_cost"].append(full_cost)
        stat["fast_cost"].append(fast_cost)
        stat["rand_cost"].append(rand_cost)
        stat["static_cost"].append(static_cost)
        stat["fast_regret"].append(full_reward - fast_reward)
        stat["rand_regret"].append(full_reward - rand_reward)
        stat["static_regret"].append(full_reward - static_reward)
        if fast_best == full_best:
            stat["fast_hit"] += 1
        if rand_best == full_best:
            stat["rand_hit"] += 1
        if static_best == full_best:
            stat["static_hit"] += 1

        history.extend(fast_runs)
        history.extend(rand_runs[:1])
        history.extend(static_runs[:1])
        history.extend(full_runs[:1])

    n = float(cfg.episodes)
    avg_full_cost = float(np.mean(stat["full_cost"]))
    avg_fast_cost = float(np.mean(stat["fast_cost"]))
    avg_rand_cost = float(np.mean(stat["rand_cost"]))
    avg_static_cost = float(np.mean(stat["static_cost"]))
    return {
        "episodes": cfg.episodes,
        "seed": cfg.seed,
        "top_k": cfg.top_k,
        "avg_cost_full": round(avg_full_cost, 4),
        "avg_cost_fast": round(avg_fast_cost, 4),
        "avg_cost_random": round(avg_rand_cost, 4),
        "avg_cost_static": round(avg_static_cost, 4),
        "cost_reduction_fast_vs_full": round((avg_full_cost - avg_fast_cost) / avg_full_cost, 4),
        "hit_rate_fast": round(stat["fast_hit"] / n, 4),
        "hit_rate_random": round(stat["rand_hit"] / n, 4),
        "hit_rate_static": round(stat["static_hit"] / n, 4),
        "avg_regret_fast": round(float(np.mean(stat["fast_regret"])), 4),
        "avg_regret_random": round(float(np.mean(stat["rand_regret"])), 4),
        "avg_regret_static": round(float(np.mean(stat["static_regret"])), 4),
    }
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=Cfg.seed)
    p.add_argument("--episodes", type=int, default=Cfg.episodes)
    p.add_argument("--warmup", type=int, default=Cfg.warmup)
    p.add_argument("--top-k", type=int, default=Cfg.top_k)
    p.add_argument("--alpha", type=float, default=Cfg.alpha)
    a = p.parse_args()
    cfg = Cfg(seed=int(a.seed), episodes=int(a.episodes), warmup=int(a.warmup), top_k=int(a.top_k), alpha=float(a.alpha))
    out = run(cfg)
    print(json_dumps(out))
    return 0


def json_dumps(x: dict[str, Any]) -> str:
    import json

    return json.dumps(x, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
