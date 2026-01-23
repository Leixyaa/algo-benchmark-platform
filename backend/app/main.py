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
from fastapi.responses import StreamingResponse
from fastapi import Query

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


@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}


def _ensure_catalog_defaults(r):
    if not list_datasets(r, limit=1):
        created = time.time()
        save_dataset(
            r,
            "ds_demo",
            {
                "dataset_id": "ds_demo",
                "name": "Demo-样例数据集",
                "type": "图像",
                "size": "10 张",
                "created_at": created,
            },
        )

    if not list_algorithms(r, limit=1):
        created = time.time()
        defaults = [
            {"algorithm_id": "alg_dn_cnn", "task": "去噪", "name": "FastNLMeans(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_denoise_bilateral", "task": "去噪", "name": "Bilateral(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_denoise_gaussian", "task": "去噪", "name": "Gaussian(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_denoise_median", "task": "去噪", "name": "Median(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_dehaze_dcp", "task": "去雾", "name": "DCP暗通道先验(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_dehaze_clahe", "task": "去雾", "name": "CLAHE(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_dehaze_gamma", "task": "去雾", "name": "Gamma(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_deblur_unsharp", "task": "去模糊", "name": "UnsharpMask(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_deblur_laplacian", "task": "去模糊", "name": "LaplacianSharpen(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_sr_bicubic", "task": "超分辨率", "name": "Bicubic(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_sr_lanczos", "task": "超分辨率", "name": "Lanczos(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_sr_nearest", "task": "超分辨率", "name": "Nearest(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_lowlight_gamma", "task": "低照度增强", "name": "Gamma(基线)", "impl": "OpenCV", "version": "v1"},
            {"algorithm_id": "alg_lowlight_clahe", "task": "低照度增强", "name": "CLAHE(基线)", "impl": "OpenCV", "version": "v1"},
        ]
        for x in defaults:
            x2 = dict(x)
            x2["created_at"] = created
            save_algorithm(r, x2["algorithm_id"], x2)


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


def _scan_dataset_on_disk(data_root: Path, dataset_id: str) -> tuple[str, str]:
    ds_dir = data_root / dataset_id
    gt_dir = ds_dir / "gt"
    if not gt_dir.exists():
        return "图像", "0 张"
    n = 0
    for p in gt_dir.iterdir():
        if p.is_file():
            suf = p.suffix.lower()
            if suf in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
                n += 1
    return "图像", f"{n} 张"


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
    t, size = _scan_dataset_on_disk(data_root, dataset_id)
    cur["type"] = t
    cur["size"] = size
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

    t, size = _scan_dataset_on_disk(data_root, dataset_id)
    cur["type"] = t
    cur["size"] = size
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.get("/algorithms")
def get_algorithms(limit: int = 500):
    r = make_redis()
    _ensure_catalog_defaults(r)
    return list_algorithms(r, limit=limit)


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


@app.post("/runs", response_model=RunOut)
def create_run(payload: RunCreate):
    r = make_redis()
    run_id = uuid.uuid4().hex[:12]
    created = time.time()

    run = {
        "run_id": run_id,
        "task_type": payload.task_type,
        "dataset_id": payload.dataset_id,
        "algorithm_id": payload.algorithm_id,
        "params": payload.params,
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
    导出 runs（CSV / Excel）
    - 本阶段：只读 Redis 的历史 runs
    - 过滤条件：status/task_type/dataset_id/algorithm_id
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

    # ===== 扁平化表头（稳定字段，前端/论文好解释）=====
    headers = [
        "run_id",
        "task_type",
        "dataset_id",
        "algorithm_id",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "elapsed",
        "PSNR",
        "SSIM",
        "NIQE",
        "error",
        "params_json",
        "samples_json",
    ]

    def to_row(x: dict) -> dict:
        m = x.get("metrics") or {}
        params = dict(x.get("params") or {})
        params.pop("niqe_fallback", None)
        samples = x.get("samples") or []
        return {
            "run_id": x.get("run_id"),
            "task_type": x.get("task_type"),
            "dataset_id": x.get("dataset_id"),
            "algorithm_id": x.get("algorithm_id"),
            "status": x.get("status"),
            "created_at": x.get("created_at"),
            "started_at": x.get("started_at"),
            "finished_at": x.get("finished_at"),
            "elapsed": x.get("elapsed"),
            "PSNR": m.get("PSNR"),
            "SSIM": m.get("SSIM"),
            "NIQE": m.get("NIQE"),
            "error": x.get("error"),
            "params_json": json.dumps(params, ensure_ascii=False),
            "samples_json": json.dumps(samples, ensure_ascii=False),
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
    清理 runs 历史记录（默认清理已完成 done）
    - status=done：只删已完成
    - status=all：全部删除
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

