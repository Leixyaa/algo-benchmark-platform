# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Cfg:
    api_base: str = "http://127.0.0.1:8000"
    dataset_id: str = "ds_demo"
    count: int = 5
    poll_interval_s: float = 0.8
    timeout_s: float = 90.0


def _http_json(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read()
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "application/json" in ct:
                return json.loads(raw.decode("utf-8"))
            return raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        raw = e.read()
        msg = raw.decode("utf-8", errors="replace")
        raise RuntimeError(f"http_error {e.code} {url}: {msg}") from e
    except URLError as e:
        raise RuntimeError(f"network_error {url}: {e}") from e


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _create_run(cfg: Cfg, task_type: str, algorithm_id: str) -> str:
    payload = {
        "task_type": task_type,
        "dataset_id": cfg.dataset_id,
        "algorithm_id": algorithm_id,
        "params": {"metrics": ["PSNR", "SSIM", "NIQE"]},
    }
    out = _http_json("POST", f"{cfg.api_base}/runs", payload)
    rid = out.get("run_id") if isinstance(out, dict) else None
    _assert(bool(rid), f"create_run_failed: {out}")
    return str(rid)


def _poll_run(cfg: Cfg, run_id: str) -> dict[str, Any]:
    t0 = time.time()
    while True:
        out = _http_json("GET", f"{cfg.api_base}/runs/{run_id}")
        _assert(isinstance(out, dict), f"run_out_not_dict: {out}")
        status = str(out.get("status") or "").lower()
        if status in {"done", "failed", "canceled"}:
            return out
        if time.time() - t0 > cfg.timeout_s:
            raise RuntimeError(f"poll_timeout run_id={run_id} last_status={status}")
        time.sleep(cfg.poll_interval_s)


def main() -> int:
    cfg = Cfg()
    _http_json("GET", f"{cfg.api_base}/health")
    _http_json(
        "POST",
        f"{cfg.api_base}/dev/datasets/{cfg.dataset_id}/generate?task_type=all&count={cfg.count}",
    )

    matrix = [
        ("dehaze", "alg_dehaze_dcp"),
        ("denoise", "alg_dn_cnn"),
        ("deblur", "alg_dn_cnn"),
        ("sr", "alg_dn_cnn"),
        ("lowlight", "alg_dn_cnn"),
    ]

    for task_type, alg_id in matrix:
        run_id = _create_run(cfg, task_type=task_type, algorithm_id=alg_id)
        out = _poll_run(cfg, run_id)
        _assert(str(out.get("status") or "").lower() == "done", f"run_not_done {task_type}: {out.get('error')}")
        params = out.get("params") if isinstance(out.get("params"), dict) else {}
        metrics = out.get("metrics") if isinstance(out.get("metrics"), dict) else {}
        _assert(params.get("data_mode") == "real_dataset", f"unexpected_data_mode {task_type}: {params}")
        _assert(isinstance(params.get("data_used"), int) and params.get("data_used") > 0, f"bad_data_used {task_type}: {params}")
        _assert("niqe_fallback" not in params, f"niqe_fallback_should_not_exist {task_type}: {params}")
        _assert("NIQE" in metrics, f"missing_NIQE {task_type}: {metrics}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

