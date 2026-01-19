# -*- coding: gbk -*-
from __future__ import annotations

import time
import uuid
import io
import csv
import json

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import Query

from openpyxl import Workbook

from .schemas import RunCreate, RunOut
from .store import make_redis, save_run, load_run, list_runs
from .celery_app import celery_app
from .tasks import execute_run


app = FastAPI(title="Algo Eval Platform API", version="0.1.0")

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
    return runs

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
        params = x.get("params") or {}
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
    return run


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

