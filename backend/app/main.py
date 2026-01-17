from __future__ import annotations

import time
import uuid
import io
import csv
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from openpyxl import Workbook

from .schemas import RunCreate, RunOut
from .store import make_redis, save_run, load_run, list_runs
from .tasks import execute_run


app = FastAPI(title="Algo Eval Platform API", version="0.1.0")

# ����ǰ�˱��ؿ�������Vite Ĭ�� 5173��
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

        "status": "queued",
        "created_at": created,
        "started_at": None,
        "finished_at": None,
        "elapsed": None,
        "metrics": {},
        "error": None,
    }
    save_run(r, run_id, run)

    # ���� celery �첽ִ��
    execute_run.delay(run_id)

    return RunOut(**run)


@app.get("/runs", response_model=list[RunOut])
def get_runs(limit: int = 200):
    r = make_redis()
    runs = list_runs(r, limit=limit)
    return [RunOut(**x) for x in runs]

@app.get("/runs/export")
def export_runs(
    format: str = Query("csv", description="csv|xlsx"),
    status: str | None = Query(None, description="queued|running|done|failed"),
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
    ]

    def to_row(x: dict) -> dict:
        m = x.get("metrics") or {}
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


@app.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return RunOut(**run)

