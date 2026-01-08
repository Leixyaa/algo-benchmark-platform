from __future__ import annotations

import time
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import RunCreate, RunOut
from .store import make_redis, save_run, load_run, list_runs
from .tasks import execute_run

app = FastAPI(title="Algo Eval Platform API", version="0.1.0")

# 允许前端本地开发跨域（Vite 默认 5173）
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

    # 丢给 celery 异步执行
    execute_run.delay(run_id)

    return RunOut(**run)


@app.get("/runs", response_model=list[RunOut])
def get_runs(limit: int = 200):
    r = make_redis()
    runs = list_runs(r, limit=limit)
    return [RunOut(**x) for x in runs]


@app.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return RunOut(**run)
