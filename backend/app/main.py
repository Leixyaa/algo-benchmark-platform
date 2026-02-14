# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import uuid
import io
import csv
import json
import base64
import zipfile
import shutil

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse

from openpyxl import Workbook

from .schemas import (
    RunCreate,
    RunOut,
    DatasetCreate,
    DatasetOut,
    DatasetPatch,
    DatasetImportZip,
    AlgorithmCreate,
    AlgorithmOut,
    AlgorithmPatch,
    PresetCreate,
    PresetOut,
    PresetPatch,
)
from .store import (
    make_redis,
    save_run,
    load_run,
    list_runs,
    save_dataset,
    load_dataset,
    delete_dataset,
    list_datasets,
    save_algorithm,
    load_algorithm,
    delete_algorithm,
    list_algorithms,
    save_preset,
    load_preset,
    delete_preset,
    list_presets,
)
from .celery_app import celery_app
from .tasks import execute_run, _stable_seed, _make_synthetic_pair_for_task

import cv2


app = FastAPI(title="Algo Eval Platform API", version="0.1.0")

def _sanitize_run_for_api(run: dict) -> dict:
    out = dict(run)
    params = out.get("params")
    if isinstance(params, dict):
        p2 = dict(params)
        p2.pop("niqe_fallback", None)
        out["params"] = p2
    return out

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TASK_LABEL_BY_TYPE = {
    "denoise": "去噪",
    "deblur": "去模糊",
    "dehaze": "去雾",
    "sr": "超分辨率",
    "lowlight": "低照度增强",
    "video_denoise": "视频去噪",
    "video_sr": "视频超分",
}

def api_error(status_code: int, error: str, message: str, **extra):
    detail = {"error": error, "message": message}
    if extra:
        detail.update(extra)
    raise HTTPException(status_code=status_code, detail=detail)


@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


def _ensure_catalog_defaults(r):
    created = time.time()

    demo_ds = {
        "dataset_id": "ds_demo",
        "name": "Demo-样例数据集",
        "type": "图像",
        "size": "10 张",
        "created_at": created,
        "meta": {},
    }
    cur_ds = load_dataset(r, "ds_demo")
    if not cur_ds:
        save_dataset(r, "ds_demo", demo_ds)
    else:
        need_patch = False
        for k in ("name", "type", "size"):
            v = str(cur_ds.get(k) or "")
            if not v or "?" in v or "\ufffd" in v:
                cur_ds[k] = demo_ds[k]
                need_patch = True
        if need_patch:
            if not isinstance(cur_ds.get("meta"), dict):
                cur_ds["meta"] = {}
            save_dataset(r, "ds_demo", cur_ds)

    defaults = [
        {
            "algorithm_id": "alg_dn_cnn",
            "task": "去噪",
            "name": "FastNLMeans(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"nlm_h": 10, "nlm_hColor": 10, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
        },
        {
            "algorithm_id": "alg_denoise_bilateral",
            "task": "去噪",
            "name": "Bilateral(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"bilateral_d": 7, "bilateral_sigmaColor": 35, "bilateral_sigmaSpace": 35},
        },
        {
            "algorithm_id": "alg_denoise_gaussian",
            "task": "去噪",
            "name": "Gaussian(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"gaussian_sigma": 1.0},
        },
        {
            "algorithm_id": "alg_denoise_median",
            "task": "去噪",
            "name": "Median(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"median_ksize": 3},
        },
        {
            "algorithm_id": "alg_dehaze_dcp",
            "task": "去雾",
            "name": "DCP暗通道先验(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"dcp_patch": 15, "dcp_omega": 0.95, "dcp_t0": 0.1},
        },
        {
            "algorithm_id": "alg_dehaze_clahe",
            "task": "去雾",
            "name": "CLAHE(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"clahe_clip_limit": 2.0},
        },
        {
            "algorithm_id": "alg_dehaze_gamma",
            "task": "去雾",
            "name": "Gamma(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"gamma": 0.75},
        },
        {
            "algorithm_id": "alg_deblur_unsharp",
            "task": "去模糊",
            "name": "UnsharpMask(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6},
        },
        {
            "algorithm_id": "alg_deblur_laplacian",
            "task": "去模糊",
            "name": "LaplacianSharpen(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"laplacian_strength": 0.7},
        },
        {
            "algorithm_id": "alg_sr_bicubic",
            "task": "超分辨率",
            "name": "Bicubic(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {},
        },
        {
            "algorithm_id": "alg_sr_lanczos",
            "task": "超分辨率",
            "name": "Lanczos(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {},
        },
        {
            "algorithm_id": "alg_sr_nearest",
            "task": "超分辨率",
            "name": "Nearest(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {},
        },
        {
            "algorithm_id": "alg_lowlight_gamma",
            "task": "低照度增强",
            "name": "Gamma(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"lowlight_gamma": 0.6},
        },
        {
            "algorithm_id": "alg_lowlight_clahe",
            "task": "低照度增强",
            "name": "CLAHE(基线)",
            "impl": "OpenCV",
            "version": "v1",
            "default_params": {"clahe_clip_limit": 2.5},
        },
    ]
    for x in defaults:
        cur = load_algorithm(r, x["algorithm_id"])
        if not cur:
            x2 = dict(x)
            x2["created_at"] = created
            save_algorithm(r, x2["algorithm_id"], x2)
            continue
        need_patch = False
        for k in ("task", "name", "impl", "version"):
            v = str(cur.get(k) or "")
            if not v or "?" in v or "\ufffd" in v:
                cur[k] = x[k]
                need_patch = True
        if not isinstance(cur.get("default_params"), dict) and isinstance(x.get("default_params"), dict):
            cur["default_params"] = x["default_params"]
            need_patch = True
        if need_patch:
            if not isinstance(cur.get("created_at"), (int, float)):
                cur["created_at"] = created
            save_algorithm(r, x["algorithm_id"], cur)


def _safe_extract_zip_bytes(zip_bytes: bytes, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/"):
                continue
            if name.startswith("/") or name.startswith("../") or "/../" in name:
                raise HTTPException(status_code=400, detail="zip_path_traversal")
            out_path = (dest_dir / name).resolve()
            if dest_dir.resolve() not in out_path.parents and out_path != dest_dir.resolve():
                raise HTTPException(status_code=400, detail="zip_path_traversal")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _scan_dataset_on_disk(data_root: Path, dataset_id: str) -> tuple[str, str, dict]:
    ds_dir = data_root / dataset_id
    gt_dir = ds_dir / "gt"
    if not gt_dir.exists():
        return "图像", "0 张", {"supported_task_types": [], "pairs_by_task": {}, "counts_by_dir": {}}
    n = 0
    for p in gt_dir.iterdir():
        if p.is_file():
            suf = p.suffix.lower()
            if suf in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
                n += 1
    from .vision.dataset_io import IMG_EXTS, count_paired_images

    input_dir_by_task = {
        "dehaze": "hazy",
        "denoise": "noisy",
        "deblur": "blur",
        "sr": "lr",
        "lowlight": "dark",
        "video_denoise": "noisy",
        "video_sr": "lr",
    }
    counts_by_dir = {}
    for d in {"gt", *input_dir_by_task.values()}:
        dd = ds_dir / d
        if not dd.exists():
            counts_by_dir[d] = 0
            continue
        counts_by_dir[d] = sum(1 for p in dd.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS)

    pairs_by_task = {t: count_paired_images(data_root, dataset_id, input_dirname=dirn, gt_dirname="gt") for t, dirn in input_dir_by_task.items()}
    supported = sorted([t for t, c in pairs_by_task.items() if c > 0])
    meta = {"supported_task_types": supported, "pairs_by_task": pairs_by_task, "counts_by_dir": counts_by_dir}
    return "图像", f"{n} 张", meta


@app.get("/datasets")
def get_datasets(limit: int = 200):
    r = make_redis()
    _ensure_catalog_defaults(r)
    return list_datasets(r, limit=limit)


@app.post("/datasets", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate):
    r = make_redis()
    _ensure_catalog_defaults(r)
    dataset_id = (payload.dataset_id or "").strip() or f"ds_{uuid.uuid4().hex[:10]}"
    if load_dataset(r, dataset_id):
        raise HTTPException(status_code=409, detail="dataset_id_exists")
    created = time.time()
    data = {
        "dataset_id": dataset_id,
        "name": payload.name.strip(),
        "type": payload.type,
        "size": payload.size,
        "created_at": created,
        "meta": {},
    }
    save_dataset(r, dataset_id, data)
    return DatasetOut(**data)


@app.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def patch_dataset(dataset_id: str, payload: DatasetPatch):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    if payload.name is not None:
        cur["name"] = payload.name.strip()
    if payload.type is not None:
        cur["type"] = payload.type
    if payload.size is not None:
        cur["size"] = payload.size
    if not isinstance(cur.get("meta"), dict):
        cur["meta"] = {}
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str):
    r = make_redis()
    _ensure_catalog_defaults(r)
    if not load_dataset(r, dataset_id):
        raise HTTPException(status_code=404, detail="dataset_not_found")
    delete_dataset(r, dataset_id)
    return {"ok": True, "dataset_id": dataset_id}


@app.post("/datasets/{dataset_id}/scan", response_model=DatasetOut)
def scan_dataset(dataset_id: str):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    data_root = Path(__file__).resolve().parents[1] / "data"
    t, size, meta = _scan_dataset_on_disk(data_root, dataset_id)
    cur["type"] = t
    cur["size"] = size
    cur["meta"] = meta
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.post("/datasets/{dataset_id}/import_zip", response_model=DatasetOut)
def import_dataset_zip(dataset_id: str, payload: DatasetImportZip):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        created = time.time()
        cur = {
            "dataset_id": dataset_id,
            "name": dataset_id,
            "type": "图像",
            "size": "-",
            "created_at": created,
            "meta": {},
        }

    try:
        zip_bytes = base64.b64decode(payload.data_b64.encode("utf-8"), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="bad_base64")

    data_root = Path(__file__).resolve().parents[1] / "data"
    ds_dir = data_root / dataset_id
    if payload.overwrite and ds_dir.exists():
        shutil.rmtree(ds_dir)
    _safe_extract_zip_bytes(zip_bytes, ds_dir)

    t, size, meta = _scan_dataset_on_disk(data_root, dataset_id)
    cur["type"] = t
    cur["size"] = size
    cur["meta"] = meta
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.get("/algorithms")
def get_algorithms(limit: int = 500):
    r = make_redis()
    _ensure_catalog_defaults(r)
    defaults_by_id = {
        "alg_dn_cnn": {"nlm_h": 10, "nlm_hColor": 10, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
        "alg_denoise_bilateral": {"bilateral_d": 7, "bilateral_sigmaColor": 35, "bilateral_sigmaSpace": 35},
        "alg_denoise_gaussian": {"gaussian_sigma": 1.0},
        "alg_denoise_median": {"median_ksize": 3},
        "alg_dehaze_dcp": {"dcp_patch": 15, "dcp_omega": 0.95, "dcp_t0": 0.1},
        "alg_dehaze_clahe": {"clahe_clip_limit": 2.0},
        "alg_dehaze_gamma": {"gamma": 0.75},
        "alg_deblur_unsharp": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6},
        "alg_deblur_laplacian": {"laplacian_strength": 0.7},
        "alg_lowlight_gamma": {"lowlight_gamma": 0.6},
        "alg_lowlight_clahe": {"clahe_clip_limit": 2.5},
    }
    presets_by_id = {
        "alg_dn_cnn": {
            "speed": {"nlm_h": 7, "nlm_hColor": 7, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 15},
            "quality": {"nlm_h": 12, "nlm_hColor": 12, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
        },
        "alg_denoise_bilateral": {
            "speed": {"bilateral_d": 5, "bilateral_sigmaColor": 25, "bilateral_sigmaSpace": 25},
            "quality": {"bilateral_d": 9, "bilateral_sigmaColor": 50, "bilateral_sigmaSpace": 50},
        },
        "alg_denoise_gaussian": {"speed": {"gaussian_sigma": 0.8}, "quality": {"gaussian_sigma": 1.2}},
        "alg_denoise_median": {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}},
        "alg_dehaze_dcp": {"speed": {"dcp_patch": 7, "dcp_omega": 0.9, "dcp_t0": 0.12}, "quality": {"dcp_patch": 21, "dcp_omega": 0.97, "dcp_t0": 0.08}},
        "alg_dehaze_clahe": {"speed": {"clahe_clip_limit": 1.5}, "quality": {"clahe_clip_limit": 3.0}},
        "alg_dehaze_gamma": {"speed": {"gamma": 0.8}, "quality": {"gamma": 0.65}},
        "alg_deblur_unsharp": {"speed": {"unsharp_sigma": 0.8, "unsharp_amount": 1.2}, "quality": {"unsharp_sigma": 1.2, "unsharp_amount": 2.0}},
        "alg_deblur_laplacian": {"speed": {"laplacian_strength": 0.5}, "quality": {"laplacian_strength": 0.9}},
        "alg_lowlight_gamma": {"speed": {"lowlight_gamma": 0.7}, "quality": {"lowlight_gamma": 0.55}},
        "alg_lowlight_clahe": {"speed": {"clahe_clip_limit": 2.0}, "quality": {"clahe_clip_limit": 3.5}},
    }

    items = list_algorithms(r, limit=limit) or []
    out = []
    for x in items:
        alg_id = x.get("algorithm_id")
        if isinstance(alg_id, str):
            dp = x.get("default_params")
            if not isinstance(dp, dict) or not dp:
                x = {**x, "default_params": defaults_by_id.get(alg_id, {})}
            pp = x.get("param_presets")
            if not isinstance(pp, dict) or not pp:
                x = {**x, "param_presets": presets_by_id.get(alg_id, {})}
        out.append(AlgorithmOut(**x).model_dump())
    return out


@app.post("/algorithms", response_model=AlgorithmOut)
def create_algorithm(payload: AlgorithmCreate):
    r = make_redis()
    _ensure_catalog_defaults(r)
    algorithm_id = (payload.algorithm_id or "").strip() or f"alg_{uuid.uuid4().hex[:10]}"
    if load_algorithm(r, algorithm_id):
        raise HTTPException(status_code=409, detail="algorithm_id_exists")
    created = time.time()
    data = {
        "algorithm_id": algorithm_id,
        "task": payload.task,
        "name": payload.name.strip(),
        "impl": payload.impl,
        "version": payload.version,
        "created_at": created,
        "default_params": payload.default_params or {},
        "param_presets": payload.param_presets or {},
    }
    save_algorithm(r, algorithm_id, data)
    return AlgorithmOut(**data)


@app.patch("/algorithms/{algorithm_id}", response_model=AlgorithmOut)
def patch_algorithm(algorithm_id: str, payload: AlgorithmPatch):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        raise HTTPException(status_code=404, detail="algorithm_not_found")
    if payload.task is not None:
        cur["task"] = payload.task
    if payload.name is not None:
        cur["name"] = payload.name.strip()
    if payload.impl is not None:
        cur["impl"] = payload.impl
    if payload.version is not None:
        cur["version"] = payload.version
    if payload.default_params is not None:
        cur["default_params"] = payload.default_params
    if payload.param_presets is not None:
        cur["param_presets"] = payload.param_presets
    save_algorithm(r, algorithm_id, cur)
    return AlgorithmOut(**cur)


@app.delete("/algorithms/{algorithm_id}")
def remove_algorithm(algorithm_id: str):
    r = make_redis()
    _ensure_catalog_defaults(r)
    if not load_algorithm(r, algorithm_id):
        raise HTTPException(status_code=404, detail="algorithm_not_found")
    delete_algorithm(r, algorithm_id)
    return {"ok": True, "algorithm_id": algorithm_id}


@app.get("/presets")
def get_presets(limit: int = 200):
    r = make_redis()
    items = list_presets(r, limit=limit) or []
    return [PresetOut(**x).model_dump() for x in items]


@app.get("/presets/{preset_id}", response_model=PresetOut)
def get_preset(preset_id: str):
    r = make_redis()
    cur = load_preset(r, preset_id)
    if not cur:
        raise HTTPException(status_code=404, detail="preset_not_found")
    return PresetOut(**cur)


@app.post("/presets", response_model=PresetOut)
def create_preset(payload: PresetCreate):
    r = make_redis()
    preset_id = (payload.preset_id or "").strip() or f"pre_{uuid.uuid4().hex[:10]}"
    if load_preset(r, preset_id):
        raise HTTPException(status_code=409, detail="preset_id_exists")
    created = time.time()
    data = {
        "preset_id": preset_id,
        "name": payload.name.strip(),
        "task_type": payload.task_type,
        "dataset_id": payload.dataset_id,
        "algorithm_id": payload.algorithm_id,
        "metrics": payload.metrics or [],
        "params": payload.params or {},
        "created_at": created,
        "updated_at": created,
    }
    save_preset(r, preset_id, data)
    return PresetOut(**data)


@app.patch("/presets/{preset_id}", response_model=PresetOut)
def patch_preset(preset_id: str, payload: PresetPatch):
    r = make_redis()
    cur = load_preset(r, preset_id)
    if not cur:
        raise HTTPException(status_code=404, detail="preset_not_found")
    if payload.name is not None:
        cur["name"] = payload.name.strip()
    if payload.task_type is not None:
        cur["task_type"] = payload.task_type
    if payload.dataset_id is not None:
        cur["dataset_id"] = payload.dataset_id
    if payload.algorithm_id is not None:
        cur["algorithm_id"] = payload.algorithm_id
    if payload.metrics is not None:
        cur["metrics"] = payload.metrics
    if payload.params is not None:
        cur["params"] = payload.params
    cur["updated_at"] = time.time()
    save_preset(r, preset_id, cur)
    return PresetOut(**cur)


@app.delete("/presets/{preset_id}")
def remove_preset(preset_id: str):
    r = make_redis()
    if not load_preset(r, preset_id):
        raise HTTPException(status_code=404, detail="preset_not_found")
    delete_preset(r, preset_id)
    return {"ok": True, "preset_id": preset_id}


@app.post("/runs", response_model=RunOut)
def create_run(payload: RunCreate):
    r = make_redis()
    task_type = (payload.task_type or "").strip().lower()
    dataset_id = (payload.dataset_id or "").strip()
    algorithm_id = (payload.algorithm_id or "").strip()
    if task_type not in TASK_LABEL_BY_TYPE:
        api_error(400, "bad_task_type", "不支持的任务类型", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
    if not dataset_id:
        api_error(400, "dataset_id_required", "缺少 dataset_id")
    if not algorithm_id:
        api_error(400, "algorithm_id_required", "缺少 algorithm_id")

    ds = load_dataset(r, dataset_id)
    if not ds:
        api_error(404, "dataset_not_found", "数据集不存在", dataset_id=dataset_id)
    alg = load_algorithm(r, algorithm_id)
    if not alg:
        api_error(404, "algorithm_not_found", "算法不存在", algorithm_id=algorithm_id)

    expected_task = TASK_LABEL_BY_TYPE.get(task_type, "")
    if expected_task and (alg.get("task") or "").strip() != expected_task:
        api_error(
            409,
            "algorithm_task_mismatch",
            "算法任务与任务类型不匹配",
            task_type=task_type,
            task_label=TASK_LABEL_BY_TYPE.get(task_type, ""),
            expected_algorithm_task=expected_task,
            algorithm_task=(alg.get("task") or "").strip(),
        )

    if bool(getattr(payload, "strict_validate", False)):
        from .vision.dataset_io import count_paired_images

        data_root = Path(__file__).resolve().parents[1] / "data"
        input_dir_by_task = {
            "dehaze": "hazy",
            "denoise": "noisy",
            "deblur": "blur",
            "sr": "lr",
            "lowlight": "dark",
            "video_denoise": "noisy",
            "video_sr": "lr",
        }
        input_dirname = input_dir_by_task.get(task_type)
        if not input_dirname:
            api_error(400, "bad_task_type", "不支持的任务类型", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
        pair_count = count_paired_images(data_root=data_root, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt")
        if pair_count <= 0:
            api_error(
                409,
                "dataset_no_pairs_for_task",
                "当前任务无可用配对，请检查输入目录与 gt/ 同名文件并重新扫描",
                task_type=task_type,
                task_label=TASK_LABEL_BY_TYPE.get(task_type, ""),
                dataset_id=dataset_id,
                expected_dirs=[input_dirname, "gt"],
                pair_count=pair_count,
            )

    run_id = uuid.uuid4().hex[:12]
    created = time.time()

    run = {
        "run_id": run_id,
        "task_type": task_type,
        "dataset_id": dataset_id,
        "algorithm_id": algorithm_id,
        "params": payload.params,
        "strict_validate": bool(getattr(payload, "strict_validate", False)),
        "samples": [],
        "cancel_requested": False,

        "status": "queued",
        "created_at": created,
        "started_at": None,
        "finished_at": None,
        "elapsed": None,
        "metrics": {},
        "error": None,
    }
    save_run(r, run_id, run)

    execute_run.apply_async((run_id,), task_id=run_id)

    return RunOut(**run)


@app.get("/runs")
def get_runs(limit: int = 200):
    r = make_redis()
    runs = list_runs(r, limit=limit)
    return [_sanitize_run_for_api(x) for x in (runs or [])]

@app.get("/runs/export")
def export_runs(
    format: str = Query("csv", description="csv|xlsx"),
    status: str | None = Query(None, description="queued|running|canceling|canceled|done|failed"),
    task_type: str | None = Query(None, description="denoise/deblur/dehaze/sr/lowlight/video_denoise/video_sr"),
    dataset_id: str | None = Query(None),
    algorithm_id: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    导出 runs 为 CSV / Excel。
    - 从 Redis 获取 runs
    - 支持按 status/task_type/dataset_id/algorithm_id 过滤
    """
    fmt = (format or "").lower().strip()
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="format_must_be_csv_or_xlsx")

    r = make_redis()
    runs = list_runs(r, limit=limit)

    # ===== 过滤 =====
    def ok(x: dict) -> bool:
        if status and x.get("status") != status:
            return False
        if task_type and x.get("task_type") != task_type:
            return False
        if dataset_id and x.get("dataset_id") != dataset_id:
            return False
        if algorithm_id and x.get("algorithm_id") != algorithm_id:
            return False
        return True

    runs = [x for x in runs if ok(x)]

    # ===== 展平部分 params/samples 字段 =====
    headers = [
        "run_id",
        "task_type",
        "task_label",
        "dataset_id",
        "dataset_name",
        "algorithm_id",
        "algorithm_name",
        "algorithm_task",
        "batch_id",
        "batch_name",
        "param_scheme",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "elapsed",
        "strict_validate",
        "data_mode",
        "input_dir",
        "pair_total",
        "pair_used",
        "PSNR",
        "SSIM",
        "NIQE",
        "error",
        "params_json",
        "samples_json",
        "record_json",
    ]

    def to_row(x: dict) -> dict:
        m = x.get("metrics") or {}
        params = dict(x.get("params") or {})
        params.pop("niqe_fallback", None)
        samples = x.get("samples") or []
        record = x.get("record") if isinstance(x.get("record"), dict) else {}
        ds = record.get("dataset") if isinstance(record.get("dataset"), dict) else {}
        alg = record.get("algorithm") if isinstance(record.get("algorithm"), dict) else {}
        batch = record.get("batch") if isinstance(record.get("batch"), dict) else {}
        task_t = x.get("task_type")
        return {
            "run_id": x.get("run_id"),
            "task_type": x.get("task_type"),
            "task_label": TASK_LABEL_BY_TYPE.get(str(task_t or ""), ""),
            "dataset_id": x.get("dataset_id"),
            "dataset_name": ds.get("name"),
            "algorithm_id": x.get("algorithm_id"),
            "algorithm_name": alg.get("name"),
            "algorithm_task": alg.get("task"),
            "batch_id": batch.get("batch_id") or params.get("batch_id"),
            "batch_name": batch.get("batch_name") or params.get("batch_name"),
            "param_scheme": batch.get("param_scheme") or params.get("param_scheme"),
            "status": x.get("status"),
            "created_at": x.get("created_at"),
            "started_at": x.get("started_at"),
            "finished_at": x.get("finished_at"),
            "elapsed": x.get("elapsed"),
            "strict_validate": x.get("strict_validate"),
            "data_mode": record.get("data_mode"),
            "input_dir": record.get("input_dir"),
            "pair_total": record.get("pair_total"),
            "pair_used": record.get("pair_used"),
            "PSNR": m.get("PSNR"),
            "SSIM": m.get("SSIM"),
            "NIQE": m.get("NIQE"),
            "error": x.get("error"),
            "params_json": json.dumps(params, ensure_ascii=False),
            "samples_json": json.dumps(samples, ensure_ascii=False),
            "record_json": json.dumps(record, ensure_ascii=False),
        }

    rows = [to_row(x) for x in runs]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"runs_export_{ts}.{fmt}"

    # ===== CSV =====
    if fmt == "csv":
        def gen():
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            yield output.getvalue().encode("utf-8-sig")
            output.seek(0)
            output.truncate(0)

            for row in rows:
                writer.writerow(row)
                yield output.getvalue().encode("utf-8-sig")
                output.seek(0)
                output.truncate(0)

        return StreamingResponse(
            gen(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ===== XLSX =====
    wb = Workbook()
    ws = wb.active
    ws.title = "runs"

    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/runs/clear")
def clear_runs(
    status: str | None = Query("done", description="done|queued|running|failed|all"),
):
    """
    清空 runs（默认清空 done）。
    - status=done：只清空已完成
    - status=all：清空全部
    """
    r = make_redis()
    keys = r.keys("run:*")

    deleted = 0
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
        except Exception:
            continue

        if status and status != "all":
            if data.get("status") != status:
                continue

        r.delete(k)
        deleted += 1

    return {"ok": True, "deleted": deleted, "status": status}



@app.get("/runs/{run_id}")
def get_run(run_id: str):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return _sanitize_run_for_api(run)


@app.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    status = (run.get("status") or "").lower()
    if status in {"done", "failed", "canceled"}:
        return {"ok": True, "run_id": run_id, "status": status}

    run["cancel_requested"] = True
    if status == "queued":
        celery_app.control.revoke(run_id)
        finished = time.time()
        run["status"] = "canceled"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - (run.get("started_at") or run.get("created_at") or finished), 3)
        run["error"] = "已取消"
        save_run(r, run_id, run)
        return {"ok": True, "run_id": run_id, "status": "canceled"}

    run["status"] = "canceling"
    save_run(r, run_id, run)
    celery_app.control.revoke(run_id, terminate=False)
    return {"ok": True, "run_id": run_id, "status": "canceling"}


@app.post("/dev/datasets/{dataset_id}/generate")
def dev_generate_dataset(
    dataset_id: str,
    task_type: str = Query("all", description="all|denoise|deblur|dehaze|sr|lowlight"),
    count: int = Query(5, ge=1, le=50),
):
    data_root = Path(__file__).resolve().parents[1] / "data"
    input_dir_by_task = {
        "dehaze": "hazy",
        "denoise": "noisy",
        "deblur": "blur",
        "sr": "lr",
        "lowlight": "dark",
    }

    task_type_norm = (task_type or "").strip().lower()
    if task_type_norm == "all":
        tasks = ["dehaze", "denoise", "deblur", "sr", "lowlight"]
    else:
        if task_type_norm not in input_dir_by_task:
            raise HTTPException(status_code=400, detail="task_type_not_supported")
        tasks = [task_type_norm]

    created: dict[str, int] = {}
    ds_dir = data_root / dataset_id
    gt_dir = ds_dir / "gt"
    gt_dir.mkdir(parents=True, exist_ok=True)

    for t in tasks:
        inp_dir = ds_dir / input_dir_by_task[t]
        inp_dir.mkdir(parents=True, exist_ok=True)
        n_ok = 0
        for i in range(count):
            seed = _stable_seed(f"{dataset_id}|{t}|{i}")
            gt_u8, inp_u8 = _make_synthetic_pair_for_task(task_type=t, seed=seed)
            name = f"{i:03d}.png"
            ok1 = bool(cv2.imwrite(str(gt_dir / name), gt_u8))
            ok2 = bool(cv2.imwrite(str(inp_dir / name), inp_u8))
            if ok1 and ok2:
                n_ok += 1
        created[t] = n_ok

    return {
        "ok": True,
        "dataset_id": dataset_id,
        "task_type": task_type_norm,
        "count": count,
        "created": created,
    }

