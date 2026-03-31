# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _http_json(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8"))


def main() -> int:
    api_base = "http://127.0.0.1:8001"
    _http_json("GET", f"{api_base}/health")
    meta = _http_json("GET", f"{api_base}/meta/error-codes")
    items = meta.get("items") if isinstance(meta, dict) else None
    if not isinstance(items, list):
        raise RuntimeError(f"bad_meta_error_codes: {meta}")
    ok = any(isinstance(x, dict) and x.get("code") == "E_DATASET_NO_PAIR" for x in items)
    if not ok:
        raise RuntimeError("missing_error_code_in_catalog: E_DATASET_NO_PAIR")

    dataset_id = "ds_empty_test"
    try:
        _http_json(
            "POST",
            f"{api_base}/datasets",
            {"dataset_id": dataset_id, "name": "Empty-Test", "type": "image", "size": "0"},
        )
    except Exception:
        _http_json("PATCH", f"{api_base}/datasets/{dataset_id}", {"name": "Empty-Test", "type": "image", "size": "0"})

    try:
        _http_json(
            "POST",
            f"{api_base}/runs",
            {"task_type": "denoise", "dataset_id": dataset_id, "algorithm_id": "alg_denoise_gaussian", "params": {}, "strict_validate": True},
        )
        raise RuntimeError("expected_create_run_fail_but_ok")
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        detail = data.get("detail") if isinstance(data, dict) else None
        if not isinstance(detail, dict):
            raise RuntimeError(f"bad_detail: {data}")
        code = detail.get("error_code") or detail.get("error")
        if code != "E_DATASET_NO_PAIR":
            raise RuntimeError(f"unexpected_error_code: {code} detail={detail}")
        print("ok", code, detail.get("error_message") or detail.get("message"))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
