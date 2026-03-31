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
    api_base: str = "http://127.0.0.1:8001"
    dataset_id: str = "ds_cancel_smoke"
    count: int = 30
    poll_interval_s: float = 0.2
    timeout_s: float = 120.0


def _http_json(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=40) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_error {e.code} {url}: {raw}") from e
    except URLError as e:
        raise RuntimeError(f"network_error {url}: {e}") from e


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _create_run(cfg: Cfg) -> str:
    out = _http_json(
        "POST",
        f"{cfg.api_base}/runs",
        {"task_type": "dehaze", "dataset_id": cfg.dataset_id, "algorithm_id": "alg_dehaze_dcp", "params": {}, "strict_validate": True},
    )
    rid = out.get("run_id") if isinstance(out, dict) else None
    _assert(bool(rid), f"create_run_failed: {out}")
    return str(rid)


def _poll_status(cfg: Cfg, run_id: str) -> str:
    t0 = time.time()
    while True:
        out = _http_json("GET", f"{cfg.api_base}/runs/{run_id}")
        status = str(out.get("status") or "").lower() if isinstance(out, dict) else ""
        if status in {"queued", "running", "canceling", "canceled", "done", "failed"}:
            return status
        if time.time() - t0 > cfg.timeout_s:
            raise RuntimeError(f"poll_status_timeout run_id={run_id} status={status}")
        time.sleep(cfg.poll_interval_s)


def _wait_terminal(cfg: Cfg, run_id: str) -> str:
    t0 = time.time()
    while True:
        out = _http_json("GET", f"{cfg.api_base}/runs/{run_id}")
        status = str(out.get("status") or "").lower() if isinstance(out, dict) else ""
        if status in {"canceled", "done", "failed"}:
            return status
        if time.time() - t0 > cfg.timeout_s:
            raise RuntimeError(f"wait_terminal_timeout run_id={run_id} status={status}")
        time.sleep(cfg.poll_interval_s)


def _cancel(cfg: Cfg, run_id: str) -> str:
    out = _http_json("POST", f"{cfg.api_base}/runs/{run_id}/cancel")
    return str(out.get("status") or "").lower() if isinstance(out, dict) else ""


def _case_queued_cancel(cfg: Cfg) -> tuple[str, str, str]:
    rid = _create_run(cfg)
    cancel_resp = _cancel(cfg, rid)
    final = _wait_terminal(cfg, rid)
    _assert(final in {"canceled", "done"}, f"queued_cancel_bad_terminal run_id={rid} cancel={cancel_resp} final={final}")
    return rid, cancel_resp, final


def _case_running_cancel(cfg: Cfg) -> tuple[str, str, str]:
    last = ("", "", "")
    for _ in range(6):
        rid = _create_run(cfg)
        t0 = time.time()
        status = ""
        while True:
            status = _poll_status(cfg, rid)
            if status == "running":
                break
            if status in {"done", "failed", "canceled"}:
                break
            if time.time() - t0 > cfg.timeout_s:
                break
            time.sleep(cfg.poll_interval_s)
        if status != "running":
            continue
        cancel_resp = _cancel(cfg, rid)
        final = _wait_terminal(cfg, rid)
        last = (rid, cancel_resp, final)
        if final == "canceled":
            return last
    _assert(bool(last[0]), "running_cancel_case_not_observed")
    return last


def main() -> int:
    cfg = Cfg()
    _http_json("GET", f"{cfg.api_base}/health")
    try:
        _http_json(
            "POST",
            f"{cfg.api_base}/datasets",
            {"dataset_id": cfg.dataset_id, "name": "Cancel-Smoke", "type": "image", "size": "-"},
        )
    except RuntimeError as e:
        if "http_error 409" not in str(e):
            raise
    _http_json("POST", f"{cfg.api_base}/dev/datasets/{cfg.dataset_id}/generate?task_type=dehaze&count={cfg.count}")
    q = _case_queued_cancel(cfg)
    r = _case_running_cancel(cfg)
    print("ok", "queued", q[0], q[1], q[2], "running", r[0], r[1], r[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
