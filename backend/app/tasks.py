from __future__ import annotations

import random
import time
from typing import Any, Dict

from .celery_app import celery_app
from .store import make_redis, load_run, save_run


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

    # ====== 模拟耗时执行（先别接真实算法）======
    # 你可以按 task_type 模拟不同耗时
    sleep_s = random.uniform(1.2, 3.0)
    time.sleep(sleep_s)

    # ====== 模拟指标（后续替换为真实 PSNR/SSIM/NIQE）======
    # 保持格式稳定，前端 Compare 直接拿 metrics 展示即可
    psnr = round(random.uniform(20, 35), 3)
    ssim = round(random.uniform(0.70, 0.98), 4)
    niqe = round(random.uniform(2.5, 6.5), 3)  # 无参考，越低越好（后续你会用真实 NIQE）

    finished = time.time()
    run["status"] = "done"
    run["finished_at"] = finished
    run["elapsed"] = round(finished - run["started_at"], 3)
    run["metrics"] = {
        "PSNR": psnr,
        "SSIM": ssim,
        "NIQE": niqe,
    }
    save_run(r, run_id, run)
    return {"ok": True, "run_id": run_id, "metrics": run["metrics"]}
