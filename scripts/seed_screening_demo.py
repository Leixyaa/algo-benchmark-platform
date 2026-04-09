from __future__ import annotations

import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.auth import get_password_hash
from backend.app.main import _ensure_admin_account, _ensure_catalog_defaults
from backend.app.selector import FastSelectConfig, bootstrap_online_model_from_runs
from backend.app.store import (
    delete_algorithm,
    delete_dataset,
    load_algorithm,
    load_dataset,
    load_user,
    make_redis,
    save_algorithm,
    save_dataset,
    save_run,
    save_user,
)


USER_PASSWORD = "Demo@123456"
SEED_USERS = [
    ("seed_uploader_a", "user"),
    ("seed_uploader_b", "user"),
    ("seed_runner", "user"),
]
SEED_DATASET_IDS = [
    "ds_seed_demo_user_a",
    "ds_seed_demo_user_b",
]
SEED_ALGORITHM_IDS = [
    "alg_seed_demo_dn_fastnl_plus",
    "alg_seed_demo_dn_bilateral_balanced",
    "alg_seed_demo_dn_gaussian_fast",
    "alg_seed_demo_dn_median_safe",
    "alg_seed_demo_dh_dcp_pro",
    "alg_seed_demo_dh_clahe_soft",
    "alg_seed_demo_dh_gamma_balanced",
    "platform_alg_seed_demo_dn_fastnl_plus",
    "platform_alg_seed_demo_dn_bilateral_balanced",
    "platform_alg_seed_demo_dh_dcp_pro",
]
RUN_PREFIX = "run_seed_screening_demo_"
MODEL_KEYS = [
    "bandit:fast_select:denoise:v1",
    "bandit:fast_select:dehaze:v1",
]


def ensure_user(r, username: str, role: str = "user") -> None:
    cur = load_user(r, username)
    if cur:
        changed = False
        if cur.get("role") != role:
            cur["role"] = role
            changed = True
        if not cur.get("hashed_password"):
            cur["hashed_password"] = get_password_hash(USER_PASSWORD)
            changed = True
        if changed:
            save_user(r, username, cur)
        return
    save_user(
        r,
        username,
        {
            "username": username,
            "hashed_password": get_password_hash(USER_PASSWORD),
            "role": role,
            "created_at": time.time(),
        },
    )


def reset_seed_state(r) -> None:
    for dataset_id in SEED_DATASET_IDS:
        delete_dataset(r, dataset_id)
    for algorithm_id in SEED_ALGORITHM_IDS:
        delete_algorithm(r, algorithm_id)
    for key in r.keys(f"run:{RUN_PREFIX}*"):
        r.delete(key)
    for key in MODEL_KEYS:
        r.delete(key)


def clone_dataset(base_ds: dict, *, dataset_id: str, owner_id: str, name: str, description: str) -> dict:
    created_at = time.time()
    cloned = dict(base_ds)
    cloned["dataset_id"] = dataset_id
    cloned["owner_id"] = owner_id
    cloned["name"] = name
    cloned["description"] = description
    cloned["created_at"] = created_at
    cloned["updated_at"] = created_at
    cloned["visibility"] = "public"
    cloned["allow_use"] = True
    cloned["allow_download"] = True
    cloned["download_count"] = 0
    cloned["meta"] = dict(base_ds.get("meta") or {})
    cloned["storage_path"] = str(base_ds.get("storage_path") or "")
    return cloned


def algorithm_record(
    *,
    algorithm_id: str,
    owner_id: str,
    task: str,
    name: str,
    impl: str,
    description: str,
    default_params: dict,
    source_algorithm_id: str | None = None,
    source_owner_id: str | None = None,
) -> dict:
    created_at = time.time()
    return {
        "algorithm_id": algorithm_id,
        "task": task,
        "name": name,
        "impl": impl,
        "version": "v1",
        "description": description,
        "owner_id": owner_id,
        "created_at": created_at,
        "default_params": dict(default_params),
        "param_presets": {},
        "visibility": "public",
        "allow_use": True,
        "allow_download": True,
        "download_count": 0,
        "is_active": True,
        "source_algorithm_id": source_algorithm_id,
        "source_owner_id": source_owner_id,
    }


def sample_metrics(psnr: float, ssim: float, niqe: float) -> list[dict]:
    samples = []
    for idx in range(1, 4):
        jitter = (idx - 2) * 0.18
        samples.append(
            {
                "name": f"sample_{idx:02d}",
                "PSNR": round(psnr + jitter, 3),
                "SSIM": round(ssim + jitter * 0.003, 4),
                "NIQE": round(max(0.5, niqe - jitter * 0.12), 3),
            }
        )
    return samples


def make_run(
    *,
    run_id: str,
    owner_id: str,
    dataset: dict,
    algorithm: dict,
    task_type: str,
    pair_total: int,
    input_dir: str,
    created_at: float,
    elapsed: float,
    psnr: float,
    ssim: float,
    niqe: float,
) -> dict:
    started_at = created_at + 12.0
    finished_at = started_at + elapsed
    task_label = str(algorithm.get("task") or "")
    return {
        "run_id": run_id,
        "task_type": task_type,
        "dataset_id": str(dataset.get("dataset_id") or ""),
        "algorithm_id": str(algorithm.get("algorithm_id") or ""),
        "owner_id": owner_id,
        "strict_validate": True,
        "record": {
            "dataset": {
                "dataset_id": dataset.get("dataset_id"),
                "owner_id": dataset.get("owner_id"),
                "storage_path": dataset.get("storage_path"),
                "meta": dict(dataset.get("meta") or {}),
            },
            "algorithm": {
                "algorithm_id": algorithm.get("algorithm_id"),
                "task": task_label,
                "name": algorithm.get("name"),
                "impl": algorithm.get("impl"),
                "version": algorithm.get("version"),
            },
            "pair_total": pair_total,
            "pair_used": pair_total,
            "input_dir": input_dir,
            "data_mode": "real_dataset",
            "timing": {
                "algo_elapsed_mean": round(elapsed / max(pair_total, 1), 6),
                "metric_elapsed_mean": round(elapsed / max(pair_total, 1), 6),
                "data_used": pair_total,
            },
        },
        "status": "done",
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed": round(elapsed, 3),
        "metrics": {
            "PSNR": round(psnr, 3),
            "SSIM": round(ssim, 4),
            "NIQE": round(niqe, 3),
        },
        "params": {
            **dict(algorithm.get("default_params") or {}),
            "metrics": ["PSNR", "SSIM", "NIQE"],
        },
        "samples": sample_metrics(psnr, ssim, niqe),
        "error": None,
        "error_code": None,
        "error_detail": None,
    }


def metric_value(base: float, step: float, idx: int) -> float:
    return base + step * math.sin(idx * 1.17)


def main() -> None:
    r = make_redis()
    _ensure_admin_account(r)
    _ensure_catalog_defaults(r)
    reset_seed_state(r)

    for username, role in SEED_USERS:
        ensure_user(r, username, role)

    base_dataset = load_dataset(r, "ds_demo")
    if not base_dataset:
        raise RuntimeError("system dataset ds_demo not found")

    ds_a = clone_dataset(
        base_dataset,
        dataset_id="ds_seed_demo_user_a",
        owner_id="seed_uploader_a",
        name="用户演示数据集-A",
        description="基于系统样例数据集复制的演示上传数据集，用于快速选型验证。",
    )
    ds_b = clone_dataset(
        base_dataset,
        dataset_id="ds_seed_demo_user_b",
        owner_id="seed_uploader_b",
        name="用户演示数据集-B",
        description="基于系统样例数据集复制的第二组演示上传数据集，用于平台审核与推荐展示。",
    )
    save_dataset(r, ds_a["dataset_id"], ds_a)
    save_dataset(r, ds_b["dataset_id"], ds_b)

    algorithms = [
        algorithm_record(
            algorithm_id="alg_seed_demo_dn_fastnl_plus",
            owner_id="seed_uploader_a",
            task="去噪",
            name="FastNLMeans(社区增强版)",
            impl="OpenCV",
            description="社区用户上传的去噪算法，模拟审核前候选算法。",
            default_params={"h": 8, "templateWindowSize": 7, "searchWindowSize": 21},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dn_bilateral_balanced",
            owner_id="seed_uploader_a",
            task="去噪",
            name="Bilateral(社区平衡版)",
            impl="OpenCV",
            description="社区用户上传的双边滤波去噪算法。",
            default_params={"d": 7, "sigmaColor": 45, "sigmaSpace": 45},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dn_gaussian_fast",
            owner_id="seed_uploader_b",
            task="去噪",
            name="Gaussian(社区快速版)",
            impl="OpenCV",
            description="社区用户上传的高斯去噪算法，速度更快但质量一般。",
            default_params={"gaussian_sigma": 1.1},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dn_median_safe",
            owner_id="seed_uploader_b",
            task="去噪",
            name="Median(社区稳妥版)",
            impl="OpenCV",
            description="社区用户上传的中值去噪算法，效果稳定但上限一般。",
            default_params={"median_ksize": 3},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dh_dcp_pro",
            owner_id="seed_uploader_a",
            task="去雾",
            name="DCP暗通道先验(社区专业版)",
            impl="OpenCV",
            description="社区用户上传的去雾算法，用于管理员审核演示。",
            default_params={"dcp_patch": 15, "omega": 0.95},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dh_clahe_soft",
            owner_id="seed_uploader_b",
            task="去雾",
            name="CLAHE(社区柔和版)",
            impl="OpenCV",
            description="社区用户上传的 CLAHE 去雾方案。",
            default_params={"clahe_clip_limit": 2.0},
        ),
        algorithm_record(
            algorithm_id="alg_seed_demo_dh_gamma_balanced",
            owner_id="seed_uploader_b",
            task="去雾",
            name="Gamma(社区平衡版)",
            impl="OpenCV",
            description="社区用户上传的 Gamma 去雾方案。",
            default_params={"gamma": 0.78},
        ),
    ]
    for item in algorithms:
        save_algorithm(r, item["algorithm_id"], item)

    promoted_algorithms = [
        algorithm_record(
            algorithm_id="platform_alg_seed_demo_dn_fastnl_plus",
            owner_id="system",
            task="去噪",
            name="FastNLMeans(社区增强版)",
            impl="OpenCV",
            description="管理员审核通过后纳入平台标准算法库的去噪算法。",
            default_params={"h": 8, "templateWindowSize": 7, "searchWindowSize": 21},
            source_algorithm_id="alg_seed_demo_dn_fastnl_plus",
            source_owner_id="seed_uploader_a",
        ),
        algorithm_record(
            algorithm_id="platform_alg_seed_demo_dn_bilateral_balanced",
            owner_id="system",
            task="去噪",
            name="Bilateral(社区平衡版)",
            impl="OpenCV",
            description="管理员审核通过后纳入平台标准算法库的双边去噪算法。",
            default_params={"d": 7, "sigmaColor": 45, "sigmaSpace": 45},
            source_algorithm_id="alg_seed_demo_dn_bilateral_balanced",
            source_owner_id="seed_uploader_a",
        ),
        algorithm_record(
            algorithm_id="platform_alg_seed_demo_dh_dcp_pro",
            owner_id="system",
            task="去雾",
            name="DCP暗通道先验(社区专业版)",
            impl="OpenCV",
            description="管理员审核通过后纳入平台标准算法库的去雾算法。",
            default_params={"dcp_patch": 15, "omega": 0.95},
            source_algorithm_id="alg_seed_demo_dh_dcp_pro",
            source_owner_id="seed_uploader_a",
        ),
    ]
    for item in promoted_algorithms:
        save_algorithm(r, item["algorithm_id"], item)

    all_run_defs = [
        ("denoise", "noisy", base_dataset, "alg_seed_demo_dn_fastnl_plus", "seed_runner", 32.1, 0.934, 2.84, 1.65, 6),
        ("denoise", "noisy", base_dataset, "alg_seed_demo_dn_bilateral_balanced", "seed_runner", 29.8, 0.896, 3.46, 1.92, 5),
        ("denoise", "noisy", base_dataset, "alg_seed_demo_dn_gaussian_fast", "seed_runner", 27.5, 0.851, 4.24, 1.12, 4),
        ("denoise", "noisy", base_dataset, "alg_seed_demo_dn_median_safe", "seed_runner", 28.4, 0.867, 3.92, 1.48, 4),
        ("denoise", "noisy", base_dataset, "platform_alg_seed_demo_dn_fastnl_plus", "seed_runner", 31.9, 0.929, 2.96, 1.72, 5),
        ("denoise", "noisy", base_dataset, "platform_alg_seed_demo_dn_bilateral_balanced", "seed_runner", 29.5, 0.891, 3.58, 1.95, 4),
        ("denoise", "noisy", base_dataset, "alg_denoise_bilateral", "seed_runner", 29.0, 0.882, 3.71, 1.83, 4),
        ("denoise", "noisy", base_dataset, "alg_denoise_gaussian", "seed_runner", 27.1, 0.842, 4.42, 1.08, 4),
        ("denoise", "noisy", base_dataset, "alg_denoise_median", "seed_runner", 28.0, 0.859, 4.01, 1.33, 4),
        ("dehaze", "hazy", base_dataset, "alg_seed_demo_dh_dcp_pro", "seed_runner", 24.9, 0.812, 4.92, 2.24, 5),
        ("dehaze", "hazy", base_dataset, "alg_seed_demo_dh_clahe_soft", "seed_runner", 22.8, 0.751, 5.64, 1.41, 4),
        ("dehaze", "hazy", base_dataset, "alg_seed_demo_dh_gamma_balanced", "seed_runner", 23.7, 0.781, 5.31, 1.36, 4),
        ("dehaze", "hazy", base_dataset, "platform_alg_seed_demo_dh_dcp_pro", "seed_runner", 24.7, 0.806, 5.01, 2.18, 4),
        ("dehaze", "hazy", base_dataset, "alg_dehaze_dcp", "seed_runner", 24.2, 0.794, 5.12, 2.11, 4),
        ("dehaze", "hazy", base_dataset, "alg_dehaze_clahe", "seed_runner", 22.4, 0.741, 5.82, 1.34, 4),
    ]

    created_runs = 0
    now = time.time() - 3600
    for task_type, input_dir, dataset, algorithm_id, owner_id, psnr_base, ssim_base, niqe_base, elapsed_base, count in all_run_defs:
        alg = load_algorithm(r, algorithm_id)
        if not alg:
            continue
        pair_total = int(((dataset.get("meta") or {}).get("pairs_by_task") or {}).get(task_type) or 5)
        for idx in range(count):
            created_at = now - (created_runs * 2700) - idx * 180
            psnr = metric_value(psnr_base, 0.42, idx)
            ssim = metric_value(ssim_base, 0.009, idx)
            niqe = metric_value(niqe_base, -0.15, idx)
            elapsed = max(0.85, metric_value(elapsed_base, 0.12, idx))
            run = make_run(
                run_id=f"{RUN_PREFIX}{task_type}_{algorithm_id}_{idx + 1:02d}",
                owner_id=owner_id,
                dataset=dataset,
                algorithm=alg,
                task_type=task_type,
                pair_total=pair_total,
                input_dir=input_dir,
                created_at=created_at,
                elapsed=elapsed,
                psnr=psnr,
                ssim=ssim,
                niqe=max(1.0, niqe),
            )
            save_run(r, run["run_id"], run)
            created_runs += 1

    cfg = FastSelectConfig()
    for task_type in ("denoise", "dehaze"):
        task_runs = []
        for key in r.keys(f"run:{RUN_PREFIX}{task_type}_*"):
            raw = r.get(key)
            if not raw:
                continue
            task_runs.append(__import__("json").loads(raw))
        bootstrap_online_model_from_runs(r, task_type=task_type, historical_runs=task_runs, config=cfg)

    print("Seeded screening demo data successfully.")
    print(f"Users: {', '.join(username for username, _ in SEED_USERS)}")
    print(f"Datasets: {', '.join(SEED_DATASET_IDS)}")
    print(f"Algorithms: {len(algorithms)} community + {len(promoted_algorithms)} platform promoted")
    print(f"Runs: {created_runs}")


if __name__ == "__main__":
    main()
