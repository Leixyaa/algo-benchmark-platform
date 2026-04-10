# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import math
from typing import Any, Callable

import cv2
import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .vision.niqe_simple import niqe_score

CALLABLE_NAMES = ("compute_metric", "evaluate_metric", "metric_fn")

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def _build_exec_globals() -> dict[str, Any]:
    return {
        "__builtins__": SAFE_BUILTINS,
        "np": np,
        "cv2": cv2,
        "math": math,
        "peak_signal_noise_ratio": peak_signal_noise_ratio,
        "structural_similarity": structural_similarity,
        "niqe_score": niqe_score,
    }


def load_metric_callable(code_text: str) -> Callable[..., Any]:
    source = str(code_text or "").strip()
    if not source:
        raise ValueError("metric_code_empty")
    scope: dict[str, Any] = {}
    exec(compile(source, "<metric_code>", "exec"), _build_exec_globals(), scope)
    for name in CALLABLE_NAMES:
        fn = scope.get(name)
        if callable(fn):
            return fn
    raise ValueError("metric_entrypoint_missing")


def validate_python_metric_code(code_text: str) -> None:
    load_metric_callable(code_text)


def execute_python_metric(
    code_text: str,
    gt_bgr_u8,
    pred_bgr_u8,
    sample_name: str = "",
    task_type: str = "",
) -> float:
    fn = load_metric_callable(code_text)
    available = {
        "gt_bgr_u8": gt_bgr_u8,
        "pred_bgr_u8": pred_bgr_u8,
        "gt": gt_bgr_u8,
        "pred": pred_bgr_u8,
        "sample_name": sample_name,
        "task_type": task_type,
    }
    signature = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
    if accepts_var_kw:
        kwargs = dict(available)
    else:
        for name, param in signature.parameters.items():
            if name in available:
                kwargs[name] = available[name]
            elif param.default is inspect._empty:
                raise ValueError(f"metric_param_unsupported:{name}")
    result = fn(**kwargs)
    if isinstance(result, dict):
        if "value" not in result:
            raise ValueError("metric_result_missing_value")
        result = result["value"]
    try:
        value = float(result)
    except Exception as exc:
        raise ValueError("metric_result_not_numeric") from exc
    if not np.isfinite(value):
        raise ValueError("metric_result_not_finite")
    return value
