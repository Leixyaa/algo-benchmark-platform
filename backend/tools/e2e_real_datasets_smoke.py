# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Cfg:
    api_base: str
    timeout_s: float = 180.0
    poll_interval_s: float = 0.8


def _http_json(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
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


def _ensure_dataset(cfg: Cfg, dataset_id: str, name: str, type_: str = "image", size: str = "-") -> None:
    payload = {"dataset_id": dataset_id, "name": name, "type": type_, "size": size}
    try:
        _http_json("POST", f"{cfg.api_base}/datasets", payload)
    except RuntimeError:
        _http_json("PATCH", f"{cfg.api_base}/datasets/{dataset_id}", {"name": name, "type": type_, "size": size})
    _http_json("POST", f"{cfg.api_base}/datasets/{dataset_id}/scan", {})


def _create_run(cfg: Cfg, task_type: str, dataset_id: str, algorithm_id: str) -> str:
    payload = {
        "task_type": task_type,
        "dataset_id": dataset_id,
        "algorithm_id": algorithm_id,
        "params": {"metrics": ["PSNR", "SSIM", "NIQE"]},
        "strict_validate": True,
    }
    out = _http_json("POST", f"{cfg.api_base}/runs", payload)
    rid = out.get("run_id") if isinstance(out, dict) else None
    if not rid:
        raise RuntimeError(f"create_run_failed: {out}")
    return str(rid)


def _poll_run(cfg: Cfg, run_id: str) -> dict[str, Any]:
    t0 = time.time()
    while True:
        out = _http_json("GET", f"{cfg.api_base}/runs/{run_id}")
        if not isinstance(out, dict):
            raise RuntimeError(f"run_out_not_dict: {out}")
        status = str(out.get("status") or "").lower()
        if status in {"done", "failed", "canceled"}:
            return out
        if time.time() - t0 > cfg.timeout_s:
            raise RuntimeError(f"poll_timeout run_id={run_id} last_status={status}")
        time.sleep(cfg.poll_interval_s)


def _assert_metrics(out: dict[str, Any], keys: list[str]) -> None:
    metrics = out.get("metrics") if isinstance(out.get("metrics"), dict) else {}
    missing = [k for k in keys if k not in metrics]
    if missing:
        raise RuntimeError(f"missing_metrics {missing}: {metrics}")


def main() -> int:
    api_base = ""
    args = sys.argv[1:]
    if "--api-base" in args:
        i = args.index("--api-base")
        if i + 1 < len(args):
            api_base = str(args[i + 1]).strip()
    if not api_base:
        api_base = os.environ.get("API_BASE", "http://127.0.0.1:8000").strip()
    cfg = Cfg(api_base=api_base)

    _http_json("GET", f"{cfg.api_base}/health")

    matrix = [
        ("dehaze", "ds_nyuhaze500", "alg_dehaze_dcp", "SOTS-Indoor(NYU-haze500)"),
        ("deblur", "ds_gopro_deblur_test", "alg_deblur_unsharp", "GoPro-Deblur-Test"),
        ("denoise", "ds_kodak24", "alg_denoise_gaussian", "Kodak24(GaussianNoise)"),
    ]

    results = []
    for task_type, dataset_id, alg_id, ds_name in matrix:
        _ensure_dataset(cfg, dataset_id=dataset_id, name=ds_name, type_="image", size="-")
        run_id = _create_run(cfg, task_type=task_type, dataset_id=dataset_id, algorithm_id=alg_id)
        out = _poll_run(cfg, run_id)
        status = str(out.get("status") or "").lower()
        if status != "done":
            raise RuntimeError(f"run_not_done task={task_type} dataset={dataset_id} alg={alg_id}: {out.get('error')}")
        _assert_metrics(out, ["PSNR", "SSIM", "NIQE"])
        metrics = out.get("metrics") if isinstance(out.get("metrics"), dict) else {}
        results.append({"task": task_type, "dataset": dataset_id, "alg": alg_id, "run_id": run_id, "metrics": metrics})

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
