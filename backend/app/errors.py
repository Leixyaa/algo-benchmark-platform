# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


E_HTTP = "E_HTTP"
E_INTERNAL = "E_INTERNAL"
E_RETRY_EXHAUSTED = "E_RETRY_EXHAUSTED"

E_BAD_TASK_TYPE = "E_BAD_TASK_TYPE"
E_DATASET_ID_REQUIRED = "E_DATASET_ID_REQUIRED"
E_ALGORITHM_ID_REQUIRED = "E_ALGORITHM_ID_REQUIRED"
E_DATASET_NOT_FOUND = "E_DATASET_NOT_FOUND"
E_ALGORITHM_NOT_FOUND = "E_ALGORITHM_NOT_FOUND"
E_ALGORITHM_TASK_MISMATCH = "E_ALGORITHM_TASK_MISMATCH"
E_DATASET_NO_PAIR = "E_DATASET_NO_PAIR"

E_ZIP_PATH_TRAVERSAL = "E_ZIP_PATH_TRAVERSAL"
E_BAD_BASE64 = "E_BAD_BASE64"
E_DATASET_ID_EXISTS = "E_DATASET_ID_EXISTS"
E_ALGORITHM_ID_EXISTS = "E_ALGORITHM_ID_EXISTS"
E_PRESET_ID_EXISTS = "E_PRESET_ID_EXISTS"
E_PRESET_NOT_FOUND = "E_PRESET_NOT_FOUND"
E_DATASET_NOT_FOUND_GENERIC = "E_DATASET_NOT_FOUND_GENERIC"
E_RUN_NOT_FOUND = "E_RUN_NOT_FOUND"
E_EXPORT_FORMAT = "E_EXPORT_FORMAT"
E_TASK_NOT_SUPPORTED = "E_TASK_NOT_SUPPORTED"

E_READ_IMAGE_FAIL = "E_READ_IMAGE_FAIL"
E_CANCELED = "E_CANCELED"


@dataclass(frozen=True)
class ErrorDef:
    code: str
    message: str
    retryable: bool = False


ERROR_DEFS: dict[str, ErrorDef] = {
    E_HTTP: ErrorDef(E_HTTP, "HTTP error", retryable=False),
    E_INTERNAL: ErrorDef(E_INTERNAL, "Internal error", retryable=True),
    E_RETRY_EXHAUSTED: ErrorDef(E_RETRY_EXHAUSTED, "retry_exhausted", retryable=False),
    E_BAD_TASK_TYPE: ErrorDef(E_BAD_TASK_TYPE, "\u4e0d\u652f\u6301\u7684\u4efb\u52a1\u7c7b\u578b", retryable=False),
    E_DATASET_ID_REQUIRED: ErrorDef(E_DATASET_ID_REQUIRED, "\u7f3a\u5c11 dataset_id", retryable=False),
    E_ALGORITHM_ID_REQUIRED: ErrorDef(E_ALGORITHM_ID_REQUIRED, "\u7f3a\u5c11 algorithm_id", retryable=False),
    E_DATASET_NOT_FOUND: ErrorDef(E_DATASET_NOT_FOUND, "\u6570\u636e\u96c6\u4e0d\u5b58\u5728", retryable=False),
    E_ALGORITHM_NOT_FOUND: ErrorDef(E_ALGORITHM_NOT_FOUND, "\u7b97\u6cd5\u4e0d\u5b58\u5728", retryable=False),
    E_ALGORITHM_TASK_MISMATCH: ErrorDef(E_ALGORITHM_TASK_MISMATCH, "\u7b97\u6cd5\u4efb\u52a1\u4e0e\u4efb\u52a1\u7c7b\u578b\u4e0d\u5339\u914d", retryable=False),
    E_DATASET_NO_PAIR: ErrorDef(E_DATASET_NO_PAIR, "\u5f53\u524d\u4efb\u52a1\u65e0\u53ef\u7528\u914d\u5bf9\uff0c\u8bf7\u68c0\u67e5\u8f93\u5165\u76ee\u5f55\u4e0e gt/ \u540c\u540d\u6587\u4ef6\u5e76\u91cd\u65b0\u626b\u63cf", retryable=False),
    E_ZIP_PATH_TRAVERSAL: ErrorDef(E_ZIP_PATH_TRAVERSAL, "zip_path_traversal", retryable=False),
    E_BAD_BASE64: ErrorDef(E_BAD_BASE64, "bad_base64", retryable=False),
    E_DATASET_ID_EXISTS: ErrorDef(E_DATASET_ID_EXISTS, "dataset_id_exists", retryable=False),
    E_ALGORITHM_ID_EXISTS: ErrorDef(E_ALGORITHM_ID_EXISTS, "algorithm_id_exists", retryable=False),
    E_PRESET_ID_EXISTS: ErrorDef(E_PRESET_ID_EXISTS, "preset_id_exists", retryable=False),
    E_PRESET_NOT_FOUND: ErrorDef(E_PRESET_NOT_FOUND, "preset_not_found", retryable=False),
    E_DATASET_NOT_FOUND_GENERIC: ErrorDef(E_DATASET_NOT_FOUND_GENERIC, "dataset_not_found", retryable=False),
    E_RUN_NOT_FOUND: ErrorDef(E_RUN_NOT_FOUND, "run_not_found", retryable=False),
    E_EXPORT_FORMAT: ErrorDef(E_EXPORT_FORMAT, "format_must_be_csv_or_xlsx", retryable=False),
    E_TASK_NOT_SUPPORTED: ErrorDef(E_TASK_NOT_SUPPORTED, "task_type_not_supported", retryable=False),
    E_READ_IMAGE_FAIL: ErrorDef(E_READ_IMAGE_FAIL, "\u8bfb\u53d6\u56fe\u7247\u5931\u8d25", retryable=False),
    E_CANCELED: ErrorDef(E_CANCELED, "\u5df2\u53d6\u6d88", retryable=False),
}


def api_error(
    status_code: int,
    error_code: str,
    message: str | None = None,
    *,
    retryable: bool | None = None,
    retry_after_s: float | None = None,
    **extra: Any,
) -> None:
    from fastapi import HTTPException

    code = str(error_code or E_HTTP)
    defn = ERROR_DEFS.get(code)
    if message is not None:
        msg = str(message)
    elif defn is not None:
        msg = str(defn.message or "")
    else:
        msg = ""
    detail: dict[str, Any] = {
        "error_code": code,
        "error_message": msg,
        "error_detail": extra or None,
        "error": code,
        "message": msg,
    }
    if retryable is None and defn is not None:
        retryable = defn.retryable
    if retryable is not None:
        detail["retryable"] = bool(retryable)
    if retry_after_s is not None:
        detail["retry_after_s"] = float(retry_after_s)
    raise HTTPException(status_code=status_code, detail=detail)


def list_error_defs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for code in sorted(ERROR_DEFS.keys()):
        d = ERROR_DEFS[code]
        out.append({"code": d.code, "message": d.message, "retryable": bool(d.retryable)})
    return out
