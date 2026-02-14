# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def _poll_run(api_base: str, run_id: str, timeout_s: float = 120.0) -> dict[str, Any]:
    t0 = time.time()
    while True:
        out = _http_json("GET", f"{api_base}/runs/{run_id}")
        if not isinstance(out, dict):
            raise RuntimeError(f"run_out_not_dict: {out}")
        status = str(out.get("status") or "").lower()
        if status in {"done", "failed", "canceled"}:
            return out
        if time.time() - t0 > timeout_s:
            raise RuntimeError(f"poll_timeout run_id={run_id} last_status={status}")
        time.sleep(0.8)


def main() -> int:
    api_base = "http://127.0.0.1:8001"
    _http_json("GET", f"{api_base}/health")

    dataset_id = "ds_kodak24"
    try:
        _http_json(
            "POST",
            f"{api_base}/datasets",
            {"dataset_id": dataset_id, "name": "Kodak24(GaussianNoise)", "type": "image", "size": "24"},
        )
    except RuntimeError:
        _http_json(
            "PATCH",
            f"{api_base}/datasets/{dataset_id}",
            {"name": "Kodak24(GaussianNoise)", "type": "image", "size": "24"},
        )

    _http_json("POST", f"{api_base}/datasets/{dataset_id}/scan", {})

    out = _http_json(
        "POST",
        f"{api_base}/runs",
        {
            "task_type": "denoise",
            "dataset_id": dataset_id,
            "algorithm_id": "alg_dn_cnn",
            "params": {"metrics": ["PSNR", "SSIM", "NIQE"]},
            "strict_validate": True,
        },
    )
    rid = out.get("run_id") if isinstance(out, dict) else None
    if not rid:
        raise RuntimeError(f"create_run_failed: {out}")

    final = _poll_run(api_base, str(rid))
    status = str(final.get("status") or "").lower()
    if status != "done":
        raise RuntimeError(f"run_not_done: {final.get('error')}")

    metrics = final.get("metrics") if isinstance(final.get("metrics"), dict) else {}
    print("done", rid, "PSNR", metrics.get("PSNR"), "SSIM", metrics.get("SSIM"), "NIQE", metrics.get("NIQE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
