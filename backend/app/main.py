# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import uuid
import io
import csv
import json
import re
import base64
import zipfile
import shutil
import os
import tempfile

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta

from openpyxl import Workbook

from .schemas import (
    RunCreate,
    RunOut,
    DatasetCreate,
    DatasetOut,
    DatasetPatch,
    DatasetIdChange,
    DatasetImportZip,
    AlgorithmCreate,
    AlgorithmOut,
    AlgorithmPatch,
    ResourceCommentCreate,
    ResourceCommentOut,
    NoticeOut,
    ReportCreate,
    ReportOut,
    ReportResolve,
    PresetCreate,
    PresetOut,
    PresetPatch,
    FastSelectRequest,
    FastSelectResponse,
    FastSelectItem,
    UserCreate,
    UserOut,
    Token,
)
from .store import (
    make_redis,
    save_run,
    load_run,
    list_runs,
    save_dataset,
    load_dataset,
    delete_dataset,
    list_datasets,
    save_algorithm,
    load_algorithm,
    delete_algorithm,
    list_algorithms,
    save_preset,
    load_preset,
    delete_preset,
    list_presets,
    save_user,
    load_user,
)
from .auth import (
    get_current_user,
    get_current_user_optional,
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from .celery_app import celery_app
from .tasks import execute_run
from .selector import (
    build_context_vector,
    fast_select_algorithms,
    fast_select_algorithms_online,
    bootstrap_online_model_from_runs,
    load_online_model,
    FastSelectConfig,
)
from . import errors as err
from .vision.dataset_access import IMG_EXTS, VIDEO_EXTS, count_paired_images, count_paired_videos, resolve_dataset_dir

import cv2


app = FastAPI(title="图像复原增强算法评测平台 API", version="0.1.0")

# --- 用户系统 (User System) ---

_ADMIN_USERNAME = os.getenv("ABP_ADMIN_USERNAME", "admin").strip() or "admin"
_ADMIN_PASSWORD = os.getenv("ABP_ADMIN_PASSWORD", "Admin@123456")


def _normalize_user_role(user: Optional[dict]) -> str:
    role = str((user or {}).get("role") or "user").strip().lower()
    return "admin" if role == "admin" else "user"


def _ensure_admin_account(r) -> dict:
    current = load_user(r, _ADMIN_USERNAME)
    if current:
        changed = False
        if _normalize_user_role(current) != "admin":
            current["role"] = "admin"
            changed = True
        if "created_at" not in current:
            current["created_at"] = time.time()
            changed = True
        if changed:
            save_user(r, _ADMIN_USERNAME, current)
        return current

    admin_user = {
        "username": _ADMIN_USERNAME,
        "hashed_password": get_password_hash(_ADMIN_PASSWORD),
        "role": "admin",
        "created_at": time.time(),
    }
    save_user(r, _ADMIN_USERNAME, admin_user)
    return admin_user


@app.post("/register", response_model=UserOut)
def register(payload: UserCreate):
    r = make_redis()
    _ensure_admin_account(r)
    username = payload.username.strip()
    if not username:
        err.api_error(400, err.E_HTTP, "username_required")
    if username.lower() == _ADMIN_USERNAME.lower():
        err.api_error(403, err.E_HTTP, "admin_username_reserved")
    if load_user(r, username):
        err.api_error(409, err.E_HTTP, "user_already_exists")
    
    user_data = {
        "username": username,
        "hashed_password": get_password_hash(payload.password),
        "role": "user",
        "created_at": time.time(),
    }
    save_user(r, username, user_data)
    return UserOut(**user_data)


@app.post("/token", response_model=Token)
@app.post("/login", response_model=Token)
def login(payload: UserCreate):
    r = make_redis()
    _ensure_admin_account(r)
    user = load_user(r, payload.username)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        err.api_error(401, err.E_HTTP, "invalid_credentials")
    if _normalize_user_role(user) == "admin":
        err.api_error(403, err.E_HTTP, "admin_use_admin_login")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "role": _normalize_user_role(user),
    }


@app.post("/admin/login", response_model=Token)
def admin_login(payload: UserCreate):
    r = make_redis()
    _ensure_admin_account(r)
    user = load_user(r, payload.username)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        err.api_error(401, err.E_HTTP, "invalid_credentials")
    if _normalize_user_role(user) != "admin":
        err.api_error(403, err.E_HTTP, "admin_only_login")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "role": "admin",
    }


@app.get("/me", response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserOut(**{**current_user, "role": _normalize_user_role(current_user)})


@app.get("/me/notices", response_model=list[NoticeOut])
def get_my_notices(
    unread_only: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    r = make_redis()
    username = _username_of(current_user)
    items = _list_notices(r, username, unread_only=unread_only)
    return [NoticeOut(**item) for item in items]


@app.post("/me/notices/{notice_id}/read")
def mark_notice_read(notice_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    username = _username_of(current_user)
    cur = _load_notice(r, username, notice_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "notice_not_found", notice_id=notice_id)
    cur["read"] = True
    _save_notice(r, username, cur)
    return {"ok": True}


def _sanitize_run_for_api(run: dict) -> dict:
    out = dict(run)
    params = out.get("params")
    if isinstance(params, dict):
        p2 = dict(params)
        p2.pop("niqe_fallback", None)
        out["params"] = p2
    return out


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        if "error_code" in detail and "error_message" in detail:
            mapped = detail
        elif "error" in detail and "message" in detail:
            extra = {k: v for k, v in detail.items() if k not in {"error", "message"}}
            mapped = {
                "error_code": str(detail.get("error") or err.E_HTTP),
                "error_message": str(detail.get("message") or ""),
                "error_detail": extra or None,
                "error": detail.get("error"),
                "message": detail.get("message"),
            }
        else:
            mapped = {
                "error_code": err.E_HTTP,
                "error_message": json.dumps(detail, ensure_ascii=False),
                "error_detail": detail,
                "error": err.E_HTTP,
                "message": json.dumps(detail, ensure_ascii=False),
            }
    else:
        msg = str(detail) if detail is not None else ""
        mapped = {"error_code": err.E_HTTP, "error_message": msg, "error_detail": None, "error": err.E_HTTP, "message": msg}
    return JSONResponse(status_code=exc.status_code, content={"detail": mapped})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境下允许所有源
    allow_credentials=False, # 设为 False 以支持 "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

TASK_LABEL_BY_TYPE = {
    "denoise": "\u53bb\u566a",
    "deblur": "\u53bb\u6a21\u7cca",
    "dehaze": "\u53bb\u96fe",
    "sr": "\u8d85\u5206\u8fa8\u7387",
    "lowlight": "\u4f4e\u7167\u5ea6\u589e\u5f3a",
    "video_denoise": "\u89c6\u9891\u53bb\u566a",
    "video_sr": "\u89c6\u9891\u8d85\u5206",
}
TASK_TYPE_BY_LABEL = {v: k for k, v in TASK_LABEL_BY_TYPE.items()}
UNKNOWN_ALGORITHM_TASK_LABEL = "\u5f85\u786e\u8ba4"

BUILTIN_ALGORITHM_IDS = {
    "alg_dn_cnn",
    "alg_dn_cnn_light",
    "alg_dn_cnn_strong",
    "alg_denoise_bilateral",
    "alg_denoise_bilateral_soft",
    "alg_denoise_bilateral_strong",
    "alg_denoise_gaussian",
    "alg_denoise_gaussian_light",
    "alg_denoise_gaussian_strong",
    "alg_denoise_median",
    "alg_denoise_median_light",
    "alg_denoise_median_strong",
    "alg_dehaze_dcp",
    "alg_dehaze_dcp_fast",
    "alg_dehaze_dcp_strong",
    "alg_dehaze_clahe",
    "alg_dehaze_clahe_mild",
    "alg_dehaze_clahe_strong",
    "alg_dehaze_gamma",
    "alg_dehaze_gamma_mild",
    "alg_dehaze_gamma_strong",
    "alg_deblur_unsharp",
    "alg_deblur_unsharp_light",
    "alg_deblur_unsharp_strong",
    "alg_deblur_laplacian",
    "alg_deblur_laplacian_light",
    "alg_deblur_laplacian_strong",
    "alg_sr_bicubic",
    "alg_sr_bicubic_sharp",
    "alg_sr_lanczos",
    "alg_sr_lanczos_sharp",
    "alg_sr_nearest",
    "alg_sr_linear",
    "alg_lowlight_gamma",
    "alg_lowlight_gamma_soft",
    "alg_lowlight_gamma_strong",
    "alg_lowlight_clahe",
    "alg_lowlight_clahe_soft",
    "alg_lowlight_clahe_strong",
    "alg_lowlight_hybrid",
    "alg_video_denoise_gaussian",
    "alg_video_denoise_gaussian_light",
    "alg_video_denoise_gaussian_strong",
    "alg_video_denoise_median",
    "alg_video_denoise_median_light",
    "alg_video_denoise_median_strong",
    "alg_video_sr_bicubic",
    "alg_video_sr_bicubic_sharp",
    "alg_video_sr_lanczos",
    "alg_video_sr_lanczos_sharp",
    "alg_video_sr_nearest",
    "alg_video_sr_linear",
}


def _normalize_algorithm_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip()).lower()


def _ensure_unique_algorithm_name(r, name: str, exclude_id: str | None = None) -> None:
    wanted = _normalize_algorithm_name(name)
    if not wanted:
        return
    for x in list_algorithms(r, limit=5000):
        aid = str(x.get("algorithm_id") or "")
        if exclude_id and aid == exclude_id:
            continue
        if _normalize_algorithm_name(x.get("name") or "") == wanted:
            err.api_error(409, err.E_ALGORITHM_ID_EXISTS, "algorithm_name_exists", algorithm_name=name, algorithm_id=aid)


def _normalize_visibility(value: str | None) -> str:
    return "public" if str(value or "").strip().lower() == "public" else "private"


def _dataset_storage_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_dataset_dir(owner_id: str, dataset_id: str) -> Path:
    return resolve_dataset_dir(_dataset_storage_root(), str(owner_id or "system"), dataset_id)


def _make_managed_dataset_dir(owner_id: str, dataset_id: str) -> Path:
    return _dataset_storage_root() / str(owner_id or "system") / dataset_id


def _normalize_storage_path(storage_path: str | None) -> str | None:
    value = str(storage_path or "").strip()
    if not value:
        return None
    return str(Path(value).expanduser())


def _dataset_dir_from_record(dataset: dict) -> Path:
    storage_path = _normalize_storage_path((dataset or {}).get("storage_path"))
    if storage_path:
        return Path(storage_path)
    owner_id = str((dataset or {}).get("owner_id") or "system")
    dataset_id = str((dataset or {}).get("dataset_id") or "")
    return _resolve_dataset_dir(owner_id, dataset_id)


def _make_unique_dataset_id(r, source_id: str, target_owner: str) -> str:
    base = str(source_id or "dataset").strip() or "dataset"
    candidate = f"{base}__{target_owner}"
    if not load_dataset(r, candidate):
        return candidate
    idx = 2
    while load_dataset(r, f"{candidate}_{idx}"):
        idx += 1
    return f"{candidate}_{idx}"


def _algorithm_name_exists(r, name: str, exclude_id: str | None = None) -> bool:
    wanted = _normalize_algorithm_name(name)
    if not wanted:
        return False
    for x in list_algorithms(r, limit=5000):
        aid = str(x.get("algorithm_id") or "")
        if exclude_id and aid == exclude_id:
            continue
        if _normalize_algorithm_name(x.get("name") or "") == wanted:
            return True
    return False


def _make_unique_algorithm_name(r, base_name: str) -> str:
    base = str(base_name or "下载算法").strip() or "下载算法"
    if not _algorithm_name_exists(r, base):
        return base
    idx = 2
    while _algorithm_name_exists(r, f"{base} #{idx}"):
        idx += 1
    return f"{base} #{idx}"


def _make_unique_algorithm_id(r, source_id: str, target_owner: str) -> str:
    base = str(source_id or "algorithm").strip() or "algorithm"
    candidate = f"{base}__{target_owner}"
    if not load_algorithm(r, candidate):
        return candidate
    idx = 2
    while load_algorithm(r, f"{candidate}_{idx}"):
        idx += 1
    return f"{candidate}_{idx}"


def _make_platform_algorithm_id(r, source_id: str) -> str:
    base = f"platform_{str(source_id or 'algorithm').strip() or 'algorithm'}"
    candidate = base
    if not load_algorithm(r, candidate):
        return candidate
    idx = 2
    while load_algorithm(r, f"{base}_{idx}"):
        idx += 1
    return f"{base}_{idx}"


@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}


@app.get("/meta/error-codes")
def meta_error_codes():
    return {"items": err.list_error_defs()}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


_CATALOG_INITIALIZED = False
_PINNED_OWNER_USERNAME = "1959920806"


def _pin_dataset_and_algorithm_owners(r) -> None:
    # 只处理没有所有者的数据集和算法
    dataset_keys = r.keys("dataset:*")
    for k in dataset_keys:
        if ":version:" in k or ":fs_hash:" in k or ":scan:" in k:
            continue
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
        except Exception:
            continue
        if not isinstance(data, dict) or "dataset_id" not in data:
            continue
        # 只有当没有所有者时，才设置为系统所有者
        if not data.get("owner_id"):
            data["owner_id"] = "system"
            save_dataset(r, str(data.get("dataset_id") or ""), data)

    algorithm_keys = r.keys("algorithm:*")
    for k in algorithm_keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
        except Exception:
            continue
        if not isinstance(data, dict) or "algorithm_id" not in data:
            continue
        alg_id = str(data.get("algorithm_id") or "")
        # 只有当没有所有者时，才设置为系统所有者或_PINNED_OWNER_USERNAME
        if not data.get("owner_id"):
            target_owner = "system" if alg_id in BUILTIN_ALGORITHM_IDS else "system"
            data["owner_id"] = target_owner
            save_algorithm(r, alg_id, data)

def _builtin_algorithm_catalog():
    items = []
    def add(algorithm_id, task, name, default_params=None, param_presets=None, impl="OpenCV", version="v1"):
        items.append({
            "algorithm_id": algorithm_id,
            "task": task,
            "name": name,
            "impl": impl,
            "version": version,
            "default_params": default_params or {},
            "param_presets": param_presets or {},
        })

    add("alg_dn_cnn", "去噪", "FastNLMeans(基线)",
        {"nlm_h": 10, "nlm_hColor": 10, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
        {"speed": {"nlm_h": 7, "nlm_hColor": 7, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 15},
         "quality": {"nlm_h": 12, "nlm_hColor": 12, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21}})
    add("alg_dn_cnn_light", "去噪", "FastNLMeans-轻度(基线)",
        {"nlm_h": 7, "nlm_hColor": 7, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 15},
        {"speed": {"nlm_h": 5, "nlm_hColor": 5, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 11},
         "quality": {"nlm_h": 9, "nlm_hColor": 9, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 17}})
    add("alg_dn_cnn_strong", "去噪", "FastNLMeans-增强(基线)",
        {"nlm_h": 14, "nlm_hColor": 14, "nlm_templateWindowSize": 9, "nlm_searchWindowSize": 25},
        {"speed": {"nlm_h": 12, "nlm_hColor": 12, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
         "quality": {"nlm_h": 16, "nlm_hColor": 16, "nlm_templateWindowSize": 11, "nlm_searchWindowSize": 31}})
    add("alg_denoise_bilateral", "去噪", "Bilateral(基线)", {"bilateral_d": 7, "bilateral_sigmaColor": 35, "bilateral_sigmaSpace": 35},
        {"speed": {"bilateral_d": 5, "bilateral_sigmaColor": 25, "bilateral_sigmaSpace": 25},
         "quality": {"bilateral_d": 9, "bilateral_sigmaColor": 50, "bilateral_sigmaSpace": 50}})
    add("alg_denoise_bilateral_soft", "去噪", "Bilateral-轻度(基线)", {"bilateral_d": 5, "bilateral_sigmaColor": 20, "bilateral_sigmaSpace": 20},
        {"speed": {"bilateral_d": 3, "bilateral_sigmaColor": 15, "bilateral_sigmaSpace": 15},
         "quality": {"bilateral_d": 7, "bilateral_sigmaColor": 28, "bilateral_sigmaSpace": 28}})
    add("alg_denoise_bilateral_strong", "去噪", "Bilateral-增强(基线)", {"bilateral_d": 11, "bilateral_sigmaColor": 60, "bilateral_sigmaSpace": 60},
        {"speed": {"bilateral_d": 9, "bilateral_sigmaColor": 50, "bilateral_sigmaSpace": 50},
         "quality": {"bilateral_d": 13, "bilateral_sigmaColor": 75, "bilateral_sigmaSpace": 75}})
    add("alg_denoise_gaussian", "去噪", "Gaussian(基线)", {"gaussian_sigma": 1.0}, {"speed": {"gaussian_sigma": 0.8}, "quality": {"gaussian_sigma": 1.2}})
    add("alg_denoise_gaussian_light", "去噪", "Gaussian-轻度(基线)", {"gaussian_sigma": 0.6}, {"speed": {"gaussian_sigma": 0.4}, "quality": {"gaussian_sigma": 0.8}})
    add("alg_denoise_gaussian_strong", "去噪", "Gaussian-增强(基线)", {"gaussian_sigma": 1.6}, {"speed": {"gaussian_sigma": 1.2}, "quality": {"gaussian_sigma": 2.0}})
    add("alg_denoise_median", "去噪", "Median(基线)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_denoise_median_light", "去噪", "Median-轻度(基线)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_denoise_median_strong", "去噪", "Median-增强(基线)", {"median_ksize": 7}, {"speed": {"median_ksize": 5}, "quality": {"median_ksize": 9}})

    add("alg_dehaze_dcp", "去雾", "DCP暗通道先验(基线)", {"dcp_patch": 15, "dcp_omega": 0.95, "dcp_t0": 0.1},
        {"speed": {"dcp_patch": 7, "dcp_omega": 0.9, "dcp_t0": 0.12}, "quality": {"dcp_patch": 21, "dcp_omega": 0.97, "dcp_t0": 0.08}})
    add("alg_dehaze_dcp_fast", "去雾", "DCP-快速(基线)", {"dcp_patch": 7, "dcp_omega": 0.9, "dcp_t0": 0.12},
        {"speed": {"dcp_patch": 5, "dcp_omega": 0.88, "dcp_t0": 0.14}, "quality": {"dcp_patch": 11, "dcp_omega": 0.93, "dcp_t0": 0.1}})
    add("alg_dehaze_dcp_strong", "去雾", "DCP-增强(基线)", {"dcp_patch": 23, "dcp_omega": 0.98, "dcp_t0": 0.08},
        {"speed": {"dcp_patch": 19, "dcp_omega": 0.96, "dcp_t0": 0.09}, "quality": {"dcp_patch": 27, "dcp_omega": 0.99, "dcp_t0": 0.06}})
    add("alg_dehaze_clahe", "去雾", "CLAHE(基线)", {"clahe_clip_limit": 2.0}, {"speed": {"clahe_clip_limit": 1.5}, "quality": {"clahe_clip_limit": 3.0}})
    add("alg_dehaze_clahe_mild", "去雾", "CLAHE-轻度(基线)", {"clahe_clip_limit": 1.5}, {"speed": {"clahe_clip_limit": 1.2}, "quality": {"clahe_clip_limit": 2.0}})
    add("alg_dehaze_clahe_strong", "去雾", "CLAHE-增强(基线)", {"clahe_clip_limit": 3.5}, {"speed": {"clahe_clip_limit": 3.0}, "quality": {"clahe_clip_limit": 4.5}})
    add("alg_dehaze_gamma", "去雾", "Gamma(基线)", {"gamma": 0.75}, {"speed": {"gamma": 0.8}, "quality": {"gamma": 0.65}})
    add("alg_dehaze_gamma_mild", "去雾", "Gamma-轻度(基线)", {"gamma": 0.85}, {"speed": {"gamma": 0.9}, "quality": {"gamma": 0.78}})
    add("alg_dehaze_gamma_strong", "去雾", "Gamma-增强(基线)", {"gamma": 0.6}, {"speed": {"gamma": 0.65}, "quality": {"gamma": 0.5}})

    add("alg_deblur_unsharp", "去模糊", "UnsharpMask(基线)", {"unsharp_sigma": 1.0, "unsharp_amount": 1.6},
        {"speed": {"unsharp_sigma": 0.8, "unsharp_amount": 1.2}, "quality": {"unsharp_sigma": 1.2, "unsharp_amount": 2.0}})
    add("alg_deblur_unsharp_light", "去模糊", "Unsharp-轻度(基线)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})
    add("alg_deblur_unsharp_strong", "去模糊", "Unsharp-增强(基线)", {"unsharp_sigma": 1.3, "unsharp_amount": 2.4},
        {"speed": {"unsharp_sigma": 1.1, "unsharp_amount": 2.0}, "quality": {"unsharp_sigma": 1.6, "unsharp_amount": 2.8}})
    add("alg_deblur_laplacian", "去模糊", "LaplacianSharpen(基线)", {"laplacian_strength": 0.7}, {"speed": {"laplacian_strength": 0.5}, "quality": {"laplacian_strength": 0.9}})
    add("alg_deblur_laplacian_light", "去模糊", "Laplacian-轻度(基线)", {"laplacian_strength": 0.5}, {"speed": {"laplacian_strength": 0.35}, "quality": {"laplacian_strength": 0.7}})
    add("alg_deblur_laplacian_strong", "去模糊", "Laplacian-增强(基线)", {"laplacian_strength": 1.1}, {"speed": {"laplacian_strength": 0.9}, "quality": {"laplacian_strength": 1.4}})

    add("alg_sr_nearest", "超分辨率", "Nearest(基线)")
    add("alg_sr_linear", "超分辨率", "Linear(基线)")
    add("alg_sr_bicubic", "超分辨率", "Bicubic(基线)")
    add("alg_sr_bicubic_sharp", "超分辨率", "Bicubic-Sharp(基线)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.3},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.1}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6}})
    add("alg_sr_lanczos", "超分辨率", "Lanczos(基线)")
    add("alg_sr_lanczos_sharp", "超分辨率", "Lanczos-Sharp(基线)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})

    add("alg_lowlight_gamma", "低照度增强", "Gamma(基线)", {"lowlight_gamma": 0.6}, {"speed": {"lowlight_gamma": 0.7}, "quality": {"lowlight_gamma": 0.55}})
    add("alg_lowlight_gamma_soft", "低照度增强", "Gamma-轻度(基线)", {"lowlight_gamma": 0.75}, {"speed": {"lowlight_gamma": 0.8}, "quality": {"lowlight_gamma": 0.65}})
    add("alg_lowlight_gamma_strong", "低照度增强", "Gamma-增强(基线)", {"lowlight_gamma": 0.45}, {"speed": {"lowlight_gamma": 0.5}, "quality": {"lowlight_gamma": 0.35}})
    add("alg_lowlight_clahe", "低照度增强", "CLAHE(基线)", {"clahe_clip_limit": 2.5}, {"speed": {"clahe_clip_limit": 2.0}, "quality": {"clahe_clip_limit": 3.5}})
    add("alg_lowlight_clahe_soft", "低照度增强", "CLAHE-轻度(基线)", {"clahe_clip_limit": 1.8}, {"speed": {"clahe_clip_limit": 1.5}, "quality": {"clahe_clip_limit": 2.4}})
    add("alg_lowlight_clahe_strong", "低照度增强", "CLAHE-增强(基线)", {"clahe_clip_limit": 3.8}, {"speed": {"clahe_clip_limit": 3.2}, "quality": {"clahe_clip_limit": 4.5}})
    add("alg_lowlight_hybrid", "低照度增强", "Gamma-CLAHE混合(基线)", {"lowlight_gamma": 0.62, "clahe_clip_limit": 2.6},
        {"speed": {"lowlight_gamma": 0.7, "clahe_clip_limit": 2.2}, "quality": {"lowlight_gamma": 0.55, "clahe_clip_limit": 3.2}})

    add("alg_video_denoise_gaussian", "视频去噪", "Video-Gaussian(基线)", {"gaussian_sigma": 1.0}, {"speed": {"gaussian_sigma": 0.8}, "quality": {"gaussian_sigma": 1.2}})
    add("alg_video_denoise_gaussian_light", "视频去噪", "Video-Gaussian-轻度(基线)", {"gaussian_sigma": 0.6}, {"speed": {"gaussian_sigma": 0.4}, "quality": {"gaussian_sigma": 0.8}})
    add("alg_video_denoise_gaussian_strong", "视频去噪", "Video-Gaussian-增强(基线)", {"gaussian_sigma": 1.6}, {"speed": {"gaussian_sigma": 1.2}, "quality": {"gaussian_sigma": 2.0}})
    add("alg_video_denoise_median", "视频去噪", "Video-Median(基线)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_video_denoise_median_light", "视频去噪", "Video-Median-轻度(基线)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_video_denoise_median_strong", "视频去噪", "Video-Median-增强(基线)", {"median_ksize": 7}, {"speed": {"median_ksize": 5}, "quality": {"median_ksize": 9}})

    add("alg_video_sr_nearest", "视频超分", "Video-Nearest(基线)")
    add("alg_video_sr_linear", "视频超分", "Video-Linear(基线)")
    add("alg_video_sr_bicubic", "视频超分", "Video-Bicubic(基线)")
    add("alg_video_sr_bicubic_sharp", "视频超分", "Video-Bicubic-Sharp(基线)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.3},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.1}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6}})
    add("alg_video_sr_lanczos", "视频超分", "Video-Lanczos(基线)")
    add("alg_video_sr_lanczos_sharp", "视频超分", "Video-Lanczos-Sharp(基线)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})
    return items

def _ensure_catalog_defaults(r):
    """
    确保 Redis 中包含默认的数据集和算法。
    使用全局变量缓存初始化状态，避免每个 API 请求都执行复杂的初始化逻辑。
    """
    global _CATALOG_INITIALIZED
    if _CATALOG_INITIALIZED:
        return
    
    # 执行初始化逻辑
    created = time.time()
    
    # 1. 默认数据集
    demo_ds_id = "ds_demo"
    demo_ds_dir = _dataset_storage_root() / "system" / demo_ds_id
    demo_type = "图像"
    demo_size = "0 张"
    demo_meta = {}
    if demo_ds_dir.exists():
        demo_type, demo_size, demo_meta = _scan_dataset_dir_on_disk(demo_ds_dir)
        demo_meta = dict(demo_meta or {})
        demo_meta["inferred_type"] = demo_type

    demo_ds = {
        "dataset_id": demo_ds_id,
        "name": "Demo-样例数据集",
        "type": demo_type,
        "size": demo_size,
        "owner_id": "system",
        "created_at": created,
        "storage_path": str(demo_ds_dir),
        "meta": demo_meta,
    }
    cur_ds = load_dataset(r, demo_ds_id)
    if not cur_ds:
        save_dataset(r, demo_ds_id, demo_ds)
    else:
        # 修复乱码或缺失字段
        need_patch = False
        for k in ("name", "type", "size"):
            v = str(cur_ds.get(k) or "")
            if not v or "?" in v or "\ufffd" in v:
                cur_ds[k] = demo_ds[k]
                need_patch = True
        cur_ds["owner_id"] = "system"
        cur_ds["storage_path"] = str(demo_ds_dir)
        if demo_size and cur_ds.get("size") != demo_size:
            cur_ds["size"] = demo_size
            need_patch = True
        if demo_type and cur_ds.get("type") != demo_type:
            cur_ds["type"] = demo_type
            need_patch = True
        if not isinstance(cur_ds.get("meta"), dict):
            cur_ds["meta"] = {}
        if demo_meta:
            cur_ds["meta"] = {**cur_ds["meta"], **demo_meta}
            need_patch = True
        if need_patch:
            save_dataset(r, demo_ds_id, cur_ds)

    # 2. 默认算法
    defaults = _builtin_algorithm_catalog()
    for x in defaults:
        cur = load_algorithm(r, x["algorithm_id"])
        if not cur:
            x2 = dict(x)
            x2["created_at"] = created
            x2["owner_id"] = "system"
            save_algorithm(r, x2["algorithm_id"], x2)
            continue
        # 增量修复逻辑
        need_patch = False
        if str(cur.get("owner_id") or "") != "system":
            cur["owner_id"] = "system"
            need_patch = True
        if not isinstance(cur.get("created_at"), (int, float)):
            cur["created_at"] = created
            need_patch = True
        if need_patch:
            save_algorithm(r, x["algorithm_id"], cur)

    _pin_dataset_and_algorithm_owners(r)
    _CATALOG_INITIALIZED = True


def _safe_extract_zip_bytes(zip_bytes: bytes, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/"):
                continue
            if name.startswith("/") or name.startswith("../") or "/../" in name:
                err.api_error(400, err.E_ZIP_PATH_TRAVERSAL, "zip_path_traversal", name=name)
            out_path = (dest_dir / name).resolve()
            if dest_dir.resolve() not in out_path.parents and out_path != dest_dir.resolve():
                err.api_error(400, err.E_ZIP_PATH_TRAVERSAL, "zip_path_traversal", name=name)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _merge_tree(src_root: Path, dst_root: Path, overwrite: bool) -> None:
    for p in src_root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src_root)
        out = dst_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not overwrite:
            continue
        if out.exists() and overwrite:
            out.unlink()
        shutil.move(str(p), str(out))


def _normalize_dataset_import_layout(ds_dir: Path, overwrite: bool) -> None:
    if (ds_dir / "gt").exists():
        return
    marker_dirs = ("gt", "hazy", "noisy", "blur", "lr", "dark")
    candidates = []
    for p in ds_dir.rglob("*"):
        if not p.is_dir():
            continue
        if p.name == "__MACOSX":
            continue
        if any((p / d).exists() for d in marker_dirs):
            depth = len(p.relative_to(ds_dir).parts)
            candidates.append((depth, p))
    if not candidates:
        return
    candidates.sort(key=lambda x: x[0])
    root = candidates[0][1]
    if root == ds_dir:
        return
    _merge_tree(root, ds_dir, overwrite=overwrite)
    shutil.rmtree(root, ignore_errors=True)


def _validate_text_encoding(v: str, field: str) -> str:
    s = (v or "").strip()
    if not s:
        return s
    if "\ufffd" in s or re.search(r"[?？]{3,}", s):
        err.api_error(
            400,
            err.E_TEXT_ENCODING_INVALID,
            "text_encoding_invalid",
            field=field,
            hint="请使用 UTF-8 提交文本",
            value_preview=s[:32],
        )
    return s


def _normalize_algorithm_task_label(value: str | None, field: str = "algorithm.task") -> str:
    s = _validate_text_encoding(value or "", field)
    if not s:
        err.api_error(
            400,
            err.E_BAD_TASK_TYPE,
            "algorithm_task_required",
            field=field,
            allowed=list(TASK_LABEL_BY_TYPE.values()),
            allowed_task_types=list(TASK_LABEL_BY_TYPE.keys()),
        )
    lower = s.lower()
    if lower in TASK_LABEL_BY_TYPE:
        return TASK_LABEL_BY_TYPE[lower]
    if s in TASK_TYPE_BY_LABEL:
        return s
    err.api_error(
        400,
        err.E_BAD_TASK_TYPE,
        "bad_algorithm_task",
        field=field,
        task=s,
        allowed=list(TASK_LABEL_BY_TYPE.values()),
        allowed_task_types=list(TASK_LABEL_BY_TYPE.keys()),
    )


def _repair_algorithm_task_label(value: str | None) -> str:
    s = str(value or "").strip()
    if not s:
        return UNKNOWN_ALGORITHM_TASK_LABEL
    lower = s.lower()
    if lower in TASK_LABEL_BY_TYPE:
        return TASK_LABEL_BY_TYPE[lower]
    if s in TASK_TYPE_BY_LABEL:
        return s
    if "\ufffd" in s or re.fullmatch(r"[?？]+", s):
        return UNKNOWN_ALGORITHM_TASK_LABEL
    return s


def _get_dataset_cache_key(dataset_id: str) -> str:
    return f"dataset:scan:{dataset_id}"


def _scan_dataset_on_disk(data_root: Path, owner_id: str, dataset_id: str) -> tuple[str, str, dict]:
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    gt_dir = ds_dir / "gt"
    if not gt_dir.exists():
        # 检查是否存在其他可能的GT目录名称
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 没有找到GT目录
            return "图像", f"0 张", {"supported_task_types": [], "pairs_by_task": {}, "counts_by_dir": {}}
    from .vision.dataset_io import IMG_EXTS, VIDEO_EXTS, count_paired_images, count_paired_videos

    input_dir_by_task = {
        "dehaze": "hazy",
        "denoise": "noisy",
        "deblur": "blur",
        "sr": "lr",
        "lowlight": "dark",
        "video_denoise": "noisy",
        "video_sr": "lr",
    }
    counts_by_dir = {}
    gt_img_count = 0
    gt_video_count = 0

    for d in {"gt", *input_dir_by_task.values()}:
        dd = ds_dir / d
        total = 0
        if dd.exists():
            for p in dd.rglob("*"):
                if not p.is_file():
                    continue
                suf = p.suffix.lower()
                if suf in IMG_EXTS:
                    total += 1
                    if d == "gt":
                        gt_img_count += 1
                elif suf in VIDEO_EXTS:
                    total += 1
                    if d == "gt":
                        gt_video_count += 1
        counts_by_dir[d] = total
    pairs_by_task = {
        "dehaze": count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="hazy", gt_dirname="gt"),
        "denoise": count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="noisy", gt_dirname="gt"),
        "deblur": count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="blur", gt_dirname="gt"),
        "sr": count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="lr", gt_dirname="gt"),
        "lowlight": count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="dark", gt_dirname="gt"),
        "video_denoise": count_paired_videos(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="noisy", gt_dirname="gt"),
        "video_sr": count_paired_videos(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="lr", gt_dirname="gt"),
    }
    supported = sorted([t for t, c in pairs_by_task.items() if c > 0])
    image_pair_total = sum(v for k, v in pairs_by_task.items() if not k.startswith("video_"))
    video_pair_total = sum(v for k, v in pairs_by_task.items() if k.startswith("video_"))
    if video_pair_total > 0 and image_pair_total > 0:
        dtype = "\u56fe\u50cf/\u89c6\u9891"
    elif video_pair_total > 0 or gt_video_count > 0:
        dtype = "\u89c6\u9891"
    else:
        dtype = "\u56fe\u50cf"
    if dtype == "\u89c6\u9891":
        size = f"{max(video_pair_total, gt_video_count)} \u6bb5"
    elif dtype == "\u56fe\u50cf/\u89c6\u9891":
        size = f"{gt_img_count} \u5f20 + {gt_video_count} \u6bb5"
    else:
        size = f"{max(image_pair_total, gt_img_count)} \u5f20"
    meta = {
        "supported_task_types": supported,
        "pairs_by_task": pairs_by_task,
        "counts_by_dir": counts_by_dir,
        "image_pair_total": image_pair_total,
        "video_pair_total": video_pair_total,
        "gt_image_count": gt_img_count,
        "gt_video_count": gt_video_count,
    }
    return dtype, size, meta


def _size_by_declared_type(declared_type: str, inferred_type: str, inferred_size: str, meta: dict) -> str:
    m = dict(meta or {})
    image_pair_total = int(m.get("image_pair_total") or 0)
    video_pair_total = int(m.get("video_pair_total") or 0)
    gt_image_count = int(m.get("gt_image_count") or 0)
    gt_video_count = int(m.get("gt_video_count") or 0)
    t = str(declared_type or "").strip()
    if t == "\u89c6\u9891":
        return f"{max(video_pair_total, gt_video_count)} \u6bb5"
    if t == "\u56fe\u50cf":
        return f"{max(image_pair_total, gt_image_count)} \u5f20"
    if t == "\u56fe\u50cf/\u89c6\u9891":
        return f"{gt_image_count} \u5f20 + {gt_video_count} \u6bb5"
    if inferred_type == "\u89c6\u9891":
        return f"{max(video_pair_total, gt_video_count)} \u6bb5"
    if inferred_type == "\u56fe\u50cf/\u89c6\u9891":
        return f"{gt_image_count} \u5f20 + {gt_video_count} \u6bb5"
    return inferred_size


def _dataset_runtime_owner_and_storage(dataset: dict | None, fallback_owner: str | None = None) -> tuple[str, str | None]:
    ds = dataset if isinstance(dataset, dict) else {}
    owner_id = str(ds.get("owner_id") or fallback_owner or "system").strip() or "system"
    storage_path = str(ds.get("storage_path") or "").strip() or None
    return owner_id, storage_path


def _username_of(current_user: Optional[dict]) -> str:
    if not isinstance(current_user, dict):
        return ""
    return str(current_user.get("username") or "").strip()


def _comment_key(resource_type: str, resource_id: str, comment_id: str) -> str:
    return f"comment:{resource_type}:{resource_id}:{comment_id}"


def _list_resource_comments(r, resource_type: str, resource_id: str) -> list[dict]:
    items: list[dict] = []
    pattern = _comment_key(resource_type, resource_id, "*")
    for key in r.scan_iter(match=pattern, count=500):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict):
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda item: float(item.get("created_at") or 0))
    return items


def _save_resource_comment(r, resource_type: str, resource_id: str, data: dict) -> None:
    comment_id = str(data.get("comment_id") or "").strip()
    if not comment_id:
        raise ValueError("comment_id_required")
    r.set(_comment_key(resource_type, resource_id, comment_id), json.dumps(data, ensure_ascii=False))


def _load_resource_comment(r, resource_type: str, resource_id: str, comment_id: str) -> Optional[dict]:
    raw = r.get(_comment_key(resource_type, resource_id, comment_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _delete_resource_comment(r, resource_type: str, resource_id: str, comment_id: str) -> None:
    r.delete(_comment_key(resource_type, resource_id, comment_id))


def _notice_key(username: str, notice_id: str) -> str:
    return f"notice:{username}:{notice_id}"


def _report_key(report_id: str) -> str:
    return f"report:{report_id}"


def _save_notice(r, username: str, data: dict) -> None:
    notice_id = str(data.get("notice_id") or "").strip()
    owner = str(username or "").strip()
    if not notice_id or not owner:
        raise ValueError("notice_key_required")
    r.set(_notice_key(owner, notice_id), json.dumps(data, ensure_ascii=False))


def _load_notice(r, username: str, notice_id: str) -> Optional[dict]:
    raw = r.get(_notice_key(username, notice_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _list_notices(r, username: str, unread_only: bool = False) -> list[dict]:
    owner = str(username or "").strip()
    if not owner:
        return []
    items: list[dict] = []
    for key in r.scan_iter(match=_notice_key(owner, "*"), count=500):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            if unread_only and bool(data.get("read")):
                continue
            items.append(data)
        except Exception:
            continue
    items.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
    return items


def _create_notice(r, username: str, title: str, content: str, *, kind: str = "info") -> dict:
    owner = str(username or "").strip()
    if not owner:
        raise ValueError("notice_username_required")
    data = {
        "notice_id": f"notice_{uuid.uuid4().hex[:12]}",
        "username": owner,
        "kind": str(kind or "info").strip() or "info",
        "title": str(title or "").strip() or "系统通知",
        "content": str(content or "").strip(),
        "created_at": time.time(),
        "read": False,
    }
    _save_notice(r, owner, data)
    return data


def _save_report(r, report_id: str, data: dict) -> None:
    r.set(_report_key(report_id), json.dumps(data, ensure_ascii=False))


def _load_report(r, report_id: str) -> Optional[dict]:
    raw = r.get(_report_key(report_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _list_reports(r) -> list[dict]:
    items: list[dict] = []
    for key in r.scan_iter(match="report:*", count=500):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("report_id"):
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
    return items


def _delete_report(r, report_id: str) -> None:
    r.delete(_report_key(report_id))


def _delete_dataset_record_with_related_state(r, dataset: dict, *, delete_disk: bool) -> bool:
    dataset_id = str((dataset or {}).get("dataset_id") or "").strip()
    if not dataset_id:
        return False
    dataset_dir = _dataset_dir_from_record(dataset)
    delete_dataset(r, dataset_id)
    r.delete(_get_dataset_cache_key(dataset_id))
    r.delete(_get_dataset_version_key(dataset_id))
    r.delete(_get_dataset_fs_hash_key(dataset_id))

    owner_id = str((dataset or {}).get("owner_id") or "").strip()
    if owner_id:
        for preset in list_presets(r, limit=5000, owner_id=owner_id) or []:
            if str(preset.get("dataset_id") or "") == dataset_id:
                delete_preset(r, str(preset.get("preset_id") or ""))

    if not delete_disk:
        return False

    try:
        storage_root = _dataset_storage_root().resolve()
        target_dir = dataset_dir.resolve()
        if storage_root == target_dir or storage_root not in [target_dir, *target_dir.parents]:
            return False
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=False)
            return True
    except Exception:
        return False
    return False


def _delete_algorithm_record_with_related_state(r, algorithm: dict) -> None:
    algorithm_id = str((algorithm or {}).get("algorithm_id") or "").strip()
    if not algorithm_id:
        return
    delete_algorithm(r, algorithm_id)
    owner_id = str((algorithm or {}).get("owner_id") or "").strip()
    if owner_id:
        for preset in list_presets(r, limit=5000, owner_id=owner_id) or []:
            if str(preset.get("algorithm_id") or "") == algorithm_id:
                delete_preset(r, str(preset.get("preset_id") or ""))


class _StreamingZipBuffer:
    def __init__(self):
        self._chunks: list[bytes] = []
        self._position = 0

    def write(self, data):
        if not data:
            return 0
        if isinstance(data, memoryview):
            data = data.tobytes()
        elif isinstance(data, bytearray):
            data = bytes(data)
        self._chunks.append(data)
        self._position += len(data)
        return len(data)

    def tell(self):
        return self._position

    def flush(self):
        return None

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def pop_chunks(self) -> bytes:
        if not self._chunks:
            return b""
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


def _stream_zipped_directory(source_dir: Path, chunk_size: int = 1024 * 1024):
    buffer = _StreamingZipBuffer()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            arcname = str(path.relative_to(source_dir))
            with zf.open(arcname, "w") as target, path.open("rb") as source:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    target.write(chunk)
                    ready = buffer.pop_chunks()
                    if ready:
                        yield ready
            ready = buffer.pop_chunks()
            if ready:
                yield ready
    ready = buffer.pop_chunks()
    if ready:
        yield ready


def _dataset_has_files(dataset_dir: Path) -> bool:
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        return False
    for path in dataset_dir.rglob("*"):
        if path.is_file():
            return True
    return False


def _list_all_dataset_records(r) -> list[dict]:
    items: list[dict] = []
    for key in r.scan_iter(match="dataset:*", count=1000):
        if ":version:" in key or ":fs_hash:" in key or ":scan:" in key:
            continue
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("dataset_id"):
                items.append(data)
        except Exception:
            continue
    return items


def _list_all_algorithm_records(r) -> list[dict]:
    items: list[dict] = []
    for key in r.scan_iter(match="algorithm:*", count=1000):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("algorithm_id"):
                items.append(data)
        except Exception:
            continue
    return items


def _assert_resource_access(resource: dict, current_user: Optional[dict], *, allow_system: bool = True) -> None:
    owner_id = str((resource or {}).get("owner_id") or "system").strip() or "system"
    username = _username_of(current_user)
    if owner_id == "system":
        if allow_system:
            return
        err.api_error(403, err.E_HTTP, "forbidden_access")
    if not username:
        err.api_error(401, err.E_HTTP, "authentication_required")
    if owner_id != username:
        err.api_error(403, err.E_HTTP, "forbidden_access")


def _assert_community_resource_visible(resource: dict, resource_type: str, resource_id: str) -> None:
    owner_id = str((resource or {}).get("owner_id") or "system").strip() or "system"
    if owner_id == "system":
        return
    if str((resource or {}).get("visibility") or "private").lower() == "public":
        return
    err.api_error(403, err.E_HTTP, f"{resource_type}_not_public", **{f"{resource_type}_id": resource_id})


def _require_admin(current_user: dict) -> None:
    if _normalize_user_role(current_user) != "admin":
        err.api_error(403, err.E_HTTP, "admin_required")


def _is_algorithm_active(algorithm: dict | None) -> bool:
    if not isinstance(algorithm, dict):
        return True
    return bool(algorithm.get("is_active", True))


def _assert_algorithm_manage_access(algorithm: dict, current_user: dict) -> None:
    owner_id = str((algorithm or {}).get("owner_id") or "system").strip() or "system"
    if owner_id == "system":
        _require_admin(current_user)
        return
    _assert_resource_access(algorithm, current_user, allow_system=False)


def _list_all_runs(r, limit: int = 5000) -> list[dict]:
    items: list[dict] = []
    for key in r.scan_iter(match="run:*", count=1000):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("run_id"):
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
    return items[:limit]


def _aggregate_dataset_meta_for_task(r, task_type: str, current_user: Optional[dict]) -> tuple[dict, int, int]:
    is_admin = _normalize_user_role(current_user) == "admin"
    if is_admin:
        datasets = list_datasets(r, limit=5000, owner_id=None, include_public=True) or []
    else:
        owner_id = _username_of(current_user) or None
        datasets = list_datasets(r, limit=5000, owner_id=owner_id, include_public=True) or []
    counts_by_dir: dict[str, int] = {}
    pairs_by_task: dict[str, int] = {}
    supported_tasks: set[str] = set()
    dataset_count = 0
    for ds in datasets:
        meta = ds.get("meta") if isinstance(ds.get("meta"), dict) else {}
        pair_map = meta.get("pairs_by_task") if isinstance(meta.get("pairs_by_task"), dict) else {}
        pair_count = int(pair_map.get(task_type) or 0)
        if pair_count <= 0:
            continue
        dataset_count += 1
        for key, value in (meta.get("counts_by_dir") if isinstance(meta.get("counts_by_dir"), dict) else {}).items():
            counts_by_dir[str(key)] = int(counts_by_dir.get(str(key), 0) or 0) + int(value or 0)
        for key, value in pair_map.items():
            k = str(key)
            v = int(value or 0)
            pairs_by_task[k] = int(pairs_by_task.get(k, 0) or 0) + v
            if v > 0:
                supported_tasks.add(k)
    meta = {
        "counts_by_dir": counts_by_dir,
        "pairs_by_task": pairs_by_task,
        "supported_task_types": sorted(supported_tasks),
    }
    return meta, int(pairs_by_task.get(task_type) or 0), dataset_count


def _list_all_comments(r) -> list[dict]:
    items: list[dict] = []
    for key in r.scan_iter(match="comment:*:*:*", count=1000):
        try:
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("comment_id"):
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
    return items


def _assert_pinned_user(current_user: dict) -> None:
    if _username_of(current_user) != _PINNED_OWNER_USERNAME:
        err.api_error(403, err.E_HTTP, "forbidden_access")


@app.get("/datasets")
def get_datasets(limit: int = 200, scope: str = Query("manage"), current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    # 管理页只返回当前用户自己的数据集；社区页单独返回公开资源
    owner_id = _username_of(current_user) or None
    include_public = str(scope or "manage").lower() == "community"
    if include_public:
        owner_id = None
        return list_datasets(r, limit=limit, owner_id=owner_id, include_public=True)

    if not owner_id:
        return []

    items = list_datasets(r, limit=limit, owner_id=owner_id, include_public=False)
    return [item for item in items if str(item.get("owner_id") or "") == owner_id][:limit]


@app.post("/datasets", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    owner_id = _username_of(current_user)
    dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
    visibility = _normalize_visibility(payload.visibility)
    allow_use = visibility == "public"
    allow_download = visibility == "public"
    existing_dataset = None
    
    if existing_dataset:
        # 检查数据集是否属于当前用户
        if str(existing_dataset.get("owner_id")) != owner_id:
            err.api_error(409, err.E_DATASET_ID_EXISTS, "dataset_id_exists", dataset_id=dataset_id)
        # 如果是当前用户的数据集，更新它
        data = {
            **existing_dataset,
            "name": _validate_text_encoding(payload.name, "dataset.name"),
            "type": _validate_text_encoding(payload.type, "dataset.type"),
            "size": _validate_text_encoding(payload.size, "dataset.size"),
            "description": _validate_text_encoding(payload.description, "dataset.description"),
            "visibility": visibility,
            "allow_use": allow_use,
            "allow_download": allow_download,
        }
    else:
        # 创建新数据集
        created = time.time()
        data = {
            "dataset_id": dataset_id,
            "name": _validate_text_encoding(payload.name, "dataset.name"),
            "type": _validate_text_encoding(payload.type, "dataset.type"),
            "size": _validate_text_encoding(payload.size, "dataset.size"),
            "description": _validate_text_encoding(payload.description, "dataset.description"),
            "storage_path": str(_make_managed_dataset_dir(owner_id, dataset_id)),
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
            "visibility": visibility,
            "allow_use": allow_use,
            "allow_download": allow_download,
            "download_count": 0,
        }
    
    save_dataset(r, dataset_id, data)
    return DatasetOut(**data)


@app.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def patch_dataset(dataset_id: str, payload: DatasetPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
        
    if payload.name is not None:
        cur["name"] = _validate_text_encoding(payload.name, "dataset.name")
    if payload.type is not None:
        cur["type"] = _validate_text_encoding(payload.type, "dataset.type")
    if payload.size is not None:
        cur["size"] = _validate_text_encoding(payload.size, "dataset.size")
    if payload.description is not None:
        cur["description"] = _validate_text_encoding(payload.description, "dataset.description")
    if payload.visibility is not None:
        cur["visibility"] = _normalize_visibility(payload.visibility)
        if str(cur.get("visibility", "private")) == "public" and not _dataset_has_files(_dataset_dir_from_record(cur)):
            err.api_error(400, err.E_HTTP, "empty_dataset_not_allowed", dataset_id=dataset_id)
    is_public = str(cur.get("visibility", "private")) == "public"
    cur["allow_use"] = is_public
    cur["allow_download"] = is_public
    if not isinstance(cur.get("meta"), dict):
        cur["meta"] = {}
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.post("/datasets/{dataset_id}/change_id", response_model=DatasetOut)
def change_dataset_id(dataset_id: str, payload: DatasetIdChange, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)

    _assert_resource_access(cur, current_user, allow_system=False)

    new_dataset_id = str(payload.new_dataset_id or "").strip()
    if not new_dataset_id:
        err.api_error(400, err.E_HTTP, "dataset_id_required")
    if new_dataset_id == dataset_id:
        return DatasetOut(**cur)
    if load_dataset(r, new_dataset_id):
        err.api_error(409, err.E_DATASET_ID_EXISTS, "dataset_id_exists", dataset_id=new_dataset_id)

    owner_id = str(cur.get("owner_id") or _username_of(current_user) or "system")
    old_dir = _dataset_dir_from_record(cur)
    new_dir = _make_managed_dataset_dir(owner_id, new_dataset_id)
    new_dir.parent.mkdir(parents=True, exist_ok=True)
    if old_dir.exists() and old_dir.resolve() != new_dir.resolve():
        if new_dir.exists():
            err.api_error(409, err.E_HTTP, "dataset_dir_already_exists", dataset_id=new_dataset_id)
        shutil.move(str(old_dir), str(new_dir))

    updated = dict(cur)
    updated["dataset_id"] = new_dataset_id
    updated["storage_path"] = str(new_dir)
    save_dataset(r, new_dataset_id, updated)
    delete_dataset(r, dataset_id)

    cache_value = r.get(_get_dataset_cache_key(dataset_id))
    if cache_value is not None:
        r.set(_get_dataset_cache_key(new_dataset_id), cache_value)
    version_value = r.get(_get_dataset_version_key(dataset_id))
    if version_value is not None:
        r.set(_get_dataset_version_key(new_dataset_id), version_value)
    fs_hash_value = r.get(_get_dataset_fs_hash_key(dataset_id))
    if fs_hash_value is not None:
        r.set(_get_dataset_fs_hash_key(new_dataset_id), fs_hash_value)
    r.delete(_get_dataset_cache_key(dataset_id))
    r.delete(_get_dataset_version_key(dataset_id))
    r.delete(_get_dataset_fs_hash_key(dataset_id))

    for preset in list_presets(r, limit=5000, owner_id=owner_id):
        if str(preset.get("dataset_id") or "") != dataset_id:
            continue
        preset_id = str(preset.get("preset_id") or "")
        if not preset_id:
            continue
        preset["dataset_id"] = new_dataset_id
        save_preset(r, preset_id, preset)

    for run in list_runs(r, limit=5000, owner_id=owner_id):
        if str(run.get("dataset_id") or "") != dataset_id:
            continue
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        run["dataset_id"] = new_dataset_id
        save_run(r, run_id, run)

    return DatasetOut(**updated)


@app.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str, delete_disk: bool = Query(False), current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
    dataset_dir = _dataset_dir_from_record(cur)
    deleted_disk = False
    delete_dataset(r, dataset_id)
    r.delete(_get_dataset_cache_key(dataset_id))
    r.delete(_get_dataset_version_key(dataset_id))
    r.delete(_get_dataset_fs_hash_key(dataset_id))
    if delete_disk:
        try:
            storage_root = _dataset_storage_root().resolve()
            target_dir = dataset_dir.resolve()
            target_dir.relative_to(storage_root)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
                deleted_disk = True
        except Exception:
            deleted_disk = False
    return {"ok": True, "dataset_id": dataset_id, "deleted_disk": deleted_disk}


@app.get("/datasets/{dataset_id}/export")
def export_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    _assert_resource_access(cur, current_user, allow_system=False)
    dataset_dir = _dataset_dir_from_record(cur)
    if not _dataset_has_files(dataset_dir):
        err.api_error(400, err.E_HTTP, "empty_dataset_not_allowed", dataset_id=dataset_id)
    filename = f"{dataset_id}.zip"
    return StreamingResponse(
        _stream_zipped_directory(dataset_dir),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/community/datasets/{dataset_id}/download", response_model=DatasetOut)
def download_dataset_to_user_library(dataset_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    source = load_dataset(r, dataset_id)
    if not source:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)

    source_owner = str(source.get("owner_id") or "system")
    visibility = str(source.get("visibility") or "private").lower()
    if source_owner != "system" and visibility != "public":
        err.api_error(403, err.E_HTTP, "dataset_not_public", dataset_id=dataset_id)
    if not bool(source.get("allow_download")) and source_owner != "system":
        err.api_error(403, err.E_HTTP, "dataset_download_not_allowed", dataset_id=dataset_id)

    target_owner = _username_of(current_user)
    if source_owner == target_owner:
        err.api_error(409, err.E_HTTP, "dataset_already_owned", dataset_id=dataset_id)
    for existing in list_datasets(r, limit=5000, owner_id=target_owner) or []:
        meta = existing.get("meta") if isinstance(existing.get("meta"), dict) else {}
        if (
            str(meta.get("downloaded_from_dataset_id") or "") == dataset_id
            and str(meta.get("downloaded_from_owner_id") or "") == source_owner
        ):
            err.api_error(409, err.E_HTTP, "dataset_already_downloaded", dataset_id=dataset_id)

    target_dataset_id = _make_unique_dataset_id(r, dataset_id, target_owner)
    source_dir = _dataset_dir_from_record(source)
    if not _dataset_has_files(source_dir):
        err.api_error(400, err.E_HTTP, "empty_dataset_not_allowed", dataset_id=dataset_id)
    target_dir = _dataset_storage_root() / target_owner / target_dataset_id
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    if source_dir.exists():
        shutil.copytree(source_dir, target_dir)
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    copied = dict(source)
    copied["dataset_id"] = target_dataset_id
    copied["owner_id"] = target_owner
    copied["source_owner_id"] = source_owner
    copied["source_dataset_id"] = dataset_id
    copied["created_at"] = time.time()
    copied["storage_path"] = str(target_dir)
    copied["visibility"] = "private"
    copied["allow_use"] = False
    copied["allow_download"] = False
    source["download_count"] = int(source.get("download_count") or 0) + 1
    save_dataset(r, dataset_id, source)
    copied["meta"] = {
        **(copied.get("meta") if isinstance(copied.get("meta"), dict) else {}),
        "downloaded_from_dataset_id": dataset_id,
        "downloaded_from_owner_id": source_owner,
        "downloaded_at": time.time(),
    }
    save_dataset(r, target_dataset_id, copied)
    return DatasetOut(**copied)


@app.get("/community/datasets/{dataset_id}/comments", response_model=list[ResourceCommentOut])
def list_dataset_comments(dataset_id: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    ds = load_dataset(r, dataset_id)
    if not ds:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    _assert_community_resource_visible(ds, "dataset", dataset_id)
    return [ResourceCommentOut(**item) for item in _list_resource_comments(r, "dataset", dataset_id)]


@app.post("/community/datasets/{dataset_id}/comments", response_model=ResourceCommentOut)
def create_dataset_comment(dataset_id: str, payload: ResourceCommentCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    ds = load_dataset(r, dataset_id)
    if not ds:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    _assert_community_resource_visible(ds, "dataset", dataset_id)
    content = _validate_text_encoding(payload.content or "", "comment.content").strip()
    if not content:
        err.api_error(400, err.E_HTTP, "comment_content_required")
    data = {
        "comment_id": f"cmt_{uuid.uuid4().hex[:12]}",
        "resource_type": "dataset",
        "resource_id": dataset_id,
        "author_id": _username_of(current_user),
        "content": content,
        "created_at": time.time(),
    }
    _save_resource_comment(r, "dataset", dataset_id, data)
    return ResourceCommentOut(**data)


@app.delete("/community/datasets/{dataset_id}/comments/{comment_id}")
def delete_dataset_comment(dataset_id: str, comment_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    ds = load_dataset(r, dataset_id)
    if not ds:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    _assert_community_resource_visible(ds, "dataset", dataset_id)
    comment = _load_resource_comment(r, "dataset", dataset_id, comment_id)
    if not comment:
        err.api_error(404, err.E_HTTP, "comment_not_found", dataset_id=dataset_id, comment_id=comment_id)
    if str(comment.get("author_id") or "") != _username_of(current_user):
        err.api_error(403, err.E_HTTP, "forbidden_access")
    _delete_resource_comment(r, "dataset", dataset_id, comment_id)
    return {"ok": True}


def _get_dataset_version_key(dataset_id: str) -> str:
    return f"dataset:version:{dataset_id}"


def _increment_dataset_version(r, dataset_id: str) -> int:
    version_key = _get_dataset_version_key(dataset_id)
    version = r.incr(version_key)
    return version


def _get_dataset_fs_hash(owner_id: str, dataset_id: str) -> str:
    """计算数据集文件系统的哈希值，用于检测文件变化"""
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    import hashlib
    import os
    
    hasher = hashlib.md5()
    
    if ds_dir.exists():
        # 遍历目录，计算文件路径和修改时间的哈希值
        for root, dirs, files in os.walk(ds_dir):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    # 获取文件修改时间
                    mtime = os.path.getmtime(file_path)
                    # 更新哈希值
                    hasher.update(f"{file_path}:{mtime}".encode('utf-8'))
                except:
                    pass
    
    return hasher.hexdigest()


def _get_dataset_fs_hash_key(dataset_id: str) -> str:
    return f"dataset:fs_hash:{dataset_id}"


def _get_dataset_fs_hash_by_dir(ds_dir: Path) -> str:
    import hashlib
    import os

    hasher = hashlib.md5()
    if ds_dir.exists():
        for root, dirs, files in os.walk(ds_dir):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(file_path)
                    hasher.update(f"{file_path}:{mtime}".encode("utf-8"))
                except Exception:
                    pass
    return hasher.hexdigest()


def _scan_dataset_dir_on_disk(ds_dir: Path) -> tuple[str, str, dict]:
    gt_dir = ds_dir / "gt"
    if not gt_dir.exists():
        for dir_name in ["groundtruth", "reference", "target"]:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            return "图像", "0 张", {"supported_task_types": [], "pairs_by_task": {}, "counts_by_dir": {}}

    input_dir_by_task = {
        "dehaze": "hazy",
        "denoise": "noisy",
        "deblur": "blur",
        "sr": "lr",
        "lowlight": "dark",
        "video_denoise": "noisy",
        "video_sr": "lr",
    }
    counts_by_dir = {}
    gt_img_count = 0
    gt_video_count = 0

    for d in {"gt", *input_dir_by_task.values()}:
        dd = ds_dir / d
        total = 0
        if dd.exists():
            for p in dd.rglob("*"):
                if not p.is_file():
                    continue
                suf = p.suffix.lower()
                if suf in IMG_EXTS:
                    total += 1
                    if d == "gt":
                        gt_img_count += 1
                elif suf in VIDEO_EXTS:
                    total += 1
                    if d == "gt":
                        gt_video_count += 1
        counts_by_dir[d] = total

    pairs_by_task = {
        "dehaze": count_paired_images(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="hazy", gt_dirname="gt", storage_path=str(ds_dir)),
        "denoise": count_paired_images(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="noisy", gt_dirname="gt", storage_path=str(ds_dir)),
        "deblur": count_paired_images(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="blur", gt_dirname="gt", storage_path=str(ds_dir)),
        "sr": count_paired_images(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="lr", gt_dirname="gt", storage_path=str(ds_dir)),
        "lowlight": count_paired_images(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="dark", gt_dirname="gt", storage_path=str(ds_dir)),
        "video_denoise": count_paired_videos(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="noisy", gt_dirname="gt", storage_path=str(ds_dir)),
        "video_sr": count_paired_videos(data_root=ds_dir.parent, owner_id="", dataset_id=ds_dir.name, input_dirname="lr", gt_dirname="gt", storage_path=str(ds_dir)),
    }
    supported = sorted([t for t, c in pairs_by_task.items() if c > 0])
    image_pair_total = sum(v for k, v in pairs_by_task.items() if not k.startswith("video_"))
    video_pair_total = sum(v for k, v in pairs_by_task.items() if k.startswith("video_"))
    if video_pair_total > 0 and image_pair_total > 0:
        dtype = "\u56fe\u50cf/\u89c6\u9891"
    elif video_pair_total > 0 or gt_video_count > 0:
        dtype = "\u89c6\u9891"
    else:
        dtype = "\u56fe\u50cf"
    if dtype == "\u89c6\u9891":
        size = f"{max(video_pair_total, gt_video_count)} \u6bb5"
    elif dtype == "\u56fe\u50cf/\u89c6\u9891":
        size = f"{gt_img_count} \u5f20 + {gt_video_count} \u6bb5"
    else:
        size = f"{max(image_pair_total, gt_img_count)} \u5f20"
    meta = {
        "supported_task_types": supported,
        "pairs_by_task": pairs_by_task,
        "counts_by_dir": counts_by_dir,
        "image_pair_total": image_pair_total,
        "video_pair_total": video_pair_total,
        "gt_image_count": gt_img_count,
        "gt_video_count": gt_video_count,
    }
    return dtype, size, meta


@app.post("/datasets/{dataset_id}/scan", response_model=DatasetOut)
def scan_dataset(
    dataset_id: str,
    force_refresh: bool = Query(False, description="是否强制刷新缓存"),
    current_user: dict = Depends(get_current_user),
):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    _assert_resource_access(cur, current_user, allow_system=True)
    
    # 获取数据集版本
    version_key = _get_dataset_version_key(dataset_id)
    current_version = r.get(version_key) or "0"
    
    # 获取数据集所有者
    owner_id = cur.get("owner_id", "system")
    # 检查文件系统变化
    fs_hash_key = _get_dataset_fs_hash_key(dataset_id)
    ds_dir = _dataset_dir_from_record(cur)
    current_fs_hash = _get_dataset_fs_hash_by_dir(ds_dir)
    cached_fs_hash = r.get(fs_hash_key)
    
    # 如果文件系统发生变化，增加版本号
    if cached_fs_hash != current_fs_hash:
        current_version = str(_increment_dataset_version(r, dataset_id))
        r.set(fs_hash_key, current_fs_hash)
    
    # 检查缓存
    cache_key = _get_dataset_cache_key(dataset_id)
    cached_data = r.get(cache_key)
    use_cache = not force_refresh
    
    if use_cache and cached_data:
        try:
            import json
            cached = json.loads(cached_data)
            # 检查缓存中的版本是否与当前版本一致
            if cached.get("version") == current_version:
                t = cached.get("type")
                size = cached.get("size")
                meta = cached.get("meta", {})
            else:
                # 版本不一致，缓存失效
                use_cache = False
        except Exception:
            use_cache = False
    else:
        use_cache = False
    
    # 如果没有缓存或缓存无效，执行扫描
    if not use_cache:
        data_root = Path(__file__).resolve().parents[1] / "data"
        # 确保数据目录存在
        data_root.mkdir(parents=True, exist_ok=True)
        # 获取数据集所有者
        owner_id = cur.get("owner_id", "system")
        # 使用用户独有的目录结构
        user_dir = data_root / owner_id
        user_dir.mkdir(parents=True, exist_ok=True)
        ds_dir.parent.mkdir(parents=True, exist_ok=True)
        t, size, meta = _scan_dataset_dir_on_disk(ds_dir)
        
        # 缓存结果，包含版本信息
        import json
        cache_data = {
            "version": current_version,
            "type": t,
            "size": size,
            "meta": meta
        }
        # 缓存永不过期，只有在数据集变化时才会失效
        r.set(cache_key, json.dumps(cache_data))
    
    existing_meta = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
    meta = {**existing_meta, **dict(meta or {})}
    meta["inferred_type"] = t
    current_type = str(cur.get("type") or "").strip()
    if not current_type:
        cur["type"] = t
        current_type = str(cur.get("type") or "").strip()
    meta["type_mismatch"] = bool(current_type and current_type != t)
    cur["size"] = _size_by_declared_type(current_type, t, size, meta)
    cur["meta"] = meta
    cur["source_owner_id"] = str(cur.get("source_owner_id") or meta.get("downloaded_from_owner_id") or "") or None
    cur["source_dataset_id"] = str(cur.get("source_dataset_id") or meta.get("downloaded_from_dataset_id") or "") or None
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.post("/datasets/{dataset_id}/import_zip", response_model=DatasetOut)
def import_dataset_zip(dataset_id: str, payload: DatasetImportZip, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        created = time.time()
        owner_id = _username_of(current_user)
        cur = {
            "dataset_id": dataset_id,
            "name": dataset_id,
            "type": "图像",
            "size": "-",
            "storage_path": str(_make_managed_dataset_dir(owner_id, dataset_id)),
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
        }
    else:
        # 从现有数据集中获取owner_id
        owner_id = cur.get("owner_id", _username_of(current_user))
    _assert_resource_access(cur, current_user, allow_system=True)

    try:
        zip_bytes = base64.b64decode(payload.data_b64.encode("utf-8"), validate=True)
    except Exception:
        err.api_error(400, err.E_BAD_BASE64, "bad_base64")

    # 使用用户独有的目录结构
    user_dir = data_root / owner_id
    # 确保数据目录存在
    ds_dir = _dataset_dir_from_record(cur)
    ds_dir.parent.mkdir(parents=True, exist_ok=True)
    if payload.overwrite and ds_dir.exists():
        shutil.rmtree(ds_dir)
    _safe_extract_zip_bytes(zip_bytes, ds_dir)
    _normalize_dataset_import_layout(ds_dir, overwrite=bool(payload.overwrite))

    cur["storage_path"] = str(ds_dir)
    t, size, meta = _scan_dataset_dir_on_disk(ds_dir)
    existing_meta = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
    meta = {**existing_meta, **dict(meta or {})}
    meta["inferred_type"] = t
    current_type = str(cur.get("type") or "").strip()
    if not current_type:
        cur["type"] = t
        current_type = str(cur.get("type") or "").strip()
    meta["type_mismatch"] = bool(current_type and current_type != t)
    cur["size"] = _size_by_declared_type(current_type, t, size, meta)
    cur["meta"] = meta
    cur["source_owner_id"] = str(cur.get("source_owner_id") or meta.get("downloaded_from_owner_id") or "") or None
    cur["source_dataset_id"] = str(cur.get("source_dataset_id") or meta.get("downloaded_from_dataset_id") or "") or None
    save_dataset(r, dataset_id, cur)
    
    # 增加数据集版本号，使缓存失效
    _increment_dataset_version(r, dataset_id)
    
    # 清除缓存，确保下次扫描获取最新数据
    cache_key = _get_dataset_cache_key(dataset_id)
    r.delete(cache_key)
    
    return DatasetOut(**cur)


@app.post("/datasets/{dataset_id}/import_zip_file", response_model=DatasetOut)
def import_dataset_zip_file(
    dataset_id: str,
    overwrite: bool = Query(False),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        created = time.time()
        owner_id = _username_of(current_user)
        cur = {
            "dataset_id": dataset_id,
            "name": dataset_id,
            "type": "图像",
            "size": "-",
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
        }
    else:
        # 从现有数据集中获取owner_id
        owner_id = cur.get("owner_id", _username_of(current_user))
    _assert_resource_access(cur, current_user, allow_system=True)
    try:
        zip_bytes = file.file.read()
    except Exception:
        err.api_error(400, err.E_BAD_BASE64, "bad_zip_file")

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 使用用户独有的目录结构
    user_dir = data_root / owner_id
    # 确保数据目录存在
    ds_dir = _dataset_dir_from_record(cur)
    ds_dir.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and ds_dir.exists():
        shutil.rmtree(ds_dir)
    _safe_extract_zip_bytes(zip_bytes, ds_dir)
    _normalize_dataset_import_layout(ds_dir, overwrite=overwrite)

    cur["storage_path"] = str(ds_dir)
    t, size, meta = _scan_dataset_dir_on_disk(ds_dir)
    existing_meta = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
    meta = {**existing_meta, **dict(meta or {})}
    meta["inferred_type"] = t
    current_type = str(cur.get("type") or "").strip()
    if not current_type:
        cur["type"] = t
        current_type = str(cur.get("type") or "").strip()
    meta["type_mismatch"] = bool(current_type and current_type != t)
    cur["size"] = _size_by_declared_type(current_type, t, size, meta)
    cur["meta"] = meta
    save_dataset(r, dataset_id, cur)
    
    # 增加数据集版本号，使缓存失效
    _increment_dataset_version(r, dataset_id)
    
    # 清除缓存，确保下次扫描获取最新数据
    cache_key = _get_dataset_cache_key(dataset_id)
    r.delete(cache_key)
    
    return DatasetOut(**cur)



@app.get("/algorithms")
def get_algorithms(limit: int = 500, scope: str = Query("manage"), current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    include_public = str(scope or "manage").lower() == "community"
    owner_id = None if include_public else (current_user["username"] if current_user else None)
    is_admin = _normalize_user_role(current_user) == "admin"
    catalog = _builtin_algorithm_catalog()
    defaults_by_id = {x["algorithm_id"]: dict(x.get("default_params") or {}) for x in catalog}
    presets_by_id = {x["algorithm_id"]: dict(x.get("param_presets") or {}) for x in catalog}

    items = list_algorithms(r, limit=limit, owner_id=owner_id, include_public=include_public) or []
    out = []
    for x in items:
        alg_id = x.get("algorithm_id")
        if isinstance(alg_id, str):
            dp = x.get("default_params")
            if not isinstance(dp, dict) or not dp:
                x = {**x, "default_params": defaults_by_id.get(alg_id, {})}
            pp = x.get("param_presets")
            if not isinstance(pp, dict) or not pp:
                x = {**x, "param_presets": presets_by_id.get(alg_id, {})}
            repaired_task = _repair_algorithm_task_label(x.get("task"))
            if repaired_task != str(x.get("task") or ""):
                x = {**x, "task": repaired_task}
                save_algorithm(r, alg_id, x)
        if not is_admin and str(x.get("owner_id") or "") == "system" and not _is_algorithm_active(x):
            continue
        out.append(AlgorithmOut(**x).model_dump())
    return out


@app.post("/algorithms", response_model=AlgorithmOut)
def create_algorithm(payload: AlgorithmCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    algorithm_id = f"alg_{uuid.uuid4().hex[:10]}"
    existing_algorithm = None
    owner_id = _username_of(current_user)
    visibility = _normalize_visibility(payload.visibility)
    allow_use = visibility == "public"
    allow_download = visibility == "public"
    
    if existing_algorithm:
        # 检查算法是否属于当前用户
        if str(existing_algorithm.get("owner_id")) != owner_id:
            err.api_error(409, err.E_ALGORITHM_ID_EXISTS, "algorithm_id_exists", algorithm_id=algorithm_id)
        # 如果是当前用户的算法，更新它
        # 确保算法名称唯一
        _ensure_unique_algorithm_name(r, payload.name, exclude_id=algorithm_id)
        data = {
            **existing_algorithm,
            "task": payload.task,
            "name": _validate_text_encoding(payload.name, "algorithm.name"),
            "impl": _validate_text_encoding(payload.impl, "algorithm.impl"),
            "version": _validate_text_encoding(payload.version, "algorithm.version"),
            "description": _validate_text_encoding(payload.description, "algorithm.description"),
            "default_params": payload.default_params or {},
            "param_presets": payload.param_presets or {},
            "visibility": visibility,
            "allow_use": allow_use,
            "allow_download": allow_download,
        }
    else:
        # 创建新算法
        # 确保算法名称唯一
        _ensure_unique_algorithm_name(r, payload.name)
        created = time.time()
        data = {
            "algorithm_id": algorithm_id,
            "task": _normalize_algorithm_task_label(payload.task),
            "name": _validate_text_encoding(payload.name, "algorithm.name"),
            "impl": _validate_text_encoding(payload.impl, "algorithm.impl"),
            "version": _validate_text_encoding(payload.version, "algorithm.version"),
            "description": _validate_text_encoding(payload.description, "algorithm.description"),
            "owner_id": owner_id,
            "created_at": created,
            "default_params": payload.default_params or {},
            "param_presets": payload.param_presets or {},
            "visibility": visibility,
            "allow_use": allow_use,
            "allow_download": allow_download,
            "download_count": 0,
        }
    
    save_algorithm(r, algorithm_id, data)
    return AlgorithmOut(**data)


@app.patch("/algorithms/{algorithm_id}", response_model=AlgorithmOut)
def patch_algorithm(algorithm_id: str, payload: AlgorithmPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)

    _assert_algorithm_manage_access(cur, current_user)
        
    if payload.task is not None:
        cur["task"] = _normalize_algorithm_task_label(payload.task)
    if payload.name is not None:
        _ensure_unique_algorithm_name(r, payload.name, exclude_id=algorithm_id)
        cur["name"] = _validate_text_encoding(payload.name, "algorithm.name")
    if payload.impl is not None:
        cur["impl"] = _validate_text_encoding(payload.impl, "algorithm.impl")
    if payload.version is not None:
        cur["version"] = _validate_text_encoding(payload.version, "algorithm.version")
    if payload.description is not None:
        cur["description"] = _validate_text_encoding(payload.description, "algorithm.description")
    if payload.default_params is not None:
        cur["default_params"] = payload.default_params
    if payload.param_presets is not None:
        cur["param_presets"] = payload.param_presets
    if payload.visibility is not None:
        cur["visibility"] = _normalize_visibility(payload.visibility)
    is_public = str(cur.get("visibility", "private")) == "public"
    cur["allow_use"] = is_public
    cur["allow_download"] = is_public
    save_algorithm(r, algorithm_id, cur)
    return AlgorithmOut(**cur)


@app.delete("/algorithms/{algorithm_id}")
def remove_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)

    _assert_algorithm_manage_access(cur, current_user)

    owner_id = str(cur.get("owner_id") or "system").strip() or "system"
    if owner_id == "system":
        source_name = str(cur.get("name") or algorithm_id).strip() or algorithm_id
        for item in _list_all_algorithm_records(r):
            item_owner = str(item.get("owner_id") or "").strip()
            if item_owner in {"", "system"}:
                continue
            if str(item.get("source_algorithm_id") or "") != algorithm_id:
                continue
            if str(item.get("source_owner_id") or "") != "system":
                continue
            _delete_algorithm_record_with_related_state(r, item)
            _create_notice(
                r,
                item_owner,
                "平台算法已下架",
                f"你下载的平台注册算法“{source_name}”已被管理员下架，相关副本已从你的算法库中移除。",
                kind="warning",
            )
        if algorithm_id in BUILTIN_ALGORITHM_IDS:
            cur["is_active"] = False
            cur["visibility"] = "private"
            cur["allow_use"] = False
            cur["allow_download"] = False
            save_algorithm(r, algorithm_id, cur)
            return {"ok": True, "algorithm_id": algorithm_id, "archived": True}
        delete_algorithm(r, algorithm_id)
        return {"ok": True, "algorithm_id": algorithm_id, "archived": False}

    delete_algorithm(r, algorithm_id)
    return {"ok": True, "algorithm_id": algorithm_id, "archived": False}


@app.get("/algorithms/{algorithm_id}/export")
def export_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    _assert_resource_access(cur, current_user, allow_system=False)
    payload = {
        "algorithm_id": cur.get("algorithm_id"),
        "task": cur.get("task"),
        "name": cur.get("name"),
        "impl": cur.get("impl"),
        "version": cur.get("version"),
        "description": cur.get("description") or "",
        "default_params": cur.get("default_params") or {},
        "param_presets": cur.get("param_presets") or {},
        "owner_id": cur.get("owner_id"),
        "source_owner_id": cur.get("source_owner_id"),
        "source_algorithm_id": cur.get("source_algorithm_id"),
        "created_at": cur.get("created_at"),
    }
    filename = f"{algorithm_id}.json"
    return StreamingResponse(
        io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/community/algorithms/{algorithm_id}/download", response_model=AlgorithmOut)
def download_algorithm_to_user_library(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    source = load_algorithm(r, algorithm_id)
    if not source:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)

    source_owner = str(source.get("owner_id") or "system")
    visibility = str(source.get("visibility") or "private").lower()
    if source_owner != "system" and visibility != "public":
        err.api_error(403, err.E_HTTP, "algorithm_not_public", algorithm_id=algorithm_id)
    if not bool(source.get("allow_download")) and source_owner != "system":
        err.api_error(403, err.E_HTTP, "algorithm_download_not_allowed", algorithm_id=algorithm_id)

    target_owner = _username_of(current_user)
    if source_owner == target_owner:
        err.api_error(409, err.E_HTTP, "algorithm_already_owned", algorithm_id=algorithm_id)
    for existing in list_algorithms(r, limit=5000, owner_id=target_owner) or []:
        if (
            str(existing.get("source_algorithm_id") or "") == algorithm_id
            and str(existing.get("source_owner_id") or "") == source_owner
        ):
            err.api_error(409, err.E_HTTP, "algorithm_already_downloaded", algorithm_id=algorithm_id)

    target_algorithm_id = _make_unique_algorithm_id(r, algorithm_id, target_owner)
    target_name = _make_unique_algorithm_name(r, str(source.get("name") or "下载算法"))

    copied = dict(source)
    copied["algorithm_id"] = target_algorithm_id
    copied["owner_id"] = target_owner
    copied["name"] = target_name
    copied["created_at"] = time.time()
    copied["visibility"] = "private"
    copied["allow_use"] = False
    copied["allow_download"] = False
    source["download_count"] = int(source.get("download_count") or 0) + 1
    save_algorithm(r, algorithm_id, source)
    copied["source_algorithm_id"] = algorithm_id
    copied["source_owner_id"] = source_owner
    save_algorithm(r, target_algorithm_id, copied)
    return AlgorithmOut(**copied)


@app.get("/community/algorithms/{algorithm_id}/comments", response_model=list[ResourceCommentOut])
def list_algorithm_comments(algorithm_id: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    alg = load_algorithm(r, algorithm_id)
    if not alg:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    _assert_community_resource_visible(alg, "algorithm", algorithm_id)
    return [ResourceCommentOut(**item) for item in _list_resource_comments(r, "algorithm", algorithm_id)]


@app.post("/community/algorithms/{algorithm_id}/comments", response_model=ResourceCommentOut)
def create_algorithm_comment(algorithm_id: str, payload: ResourceCommentCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    alg = load_algorithm(r, algorithm_id)
    if not alg:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    _assert_community_resource_visible(alg, "algorithm", algorithm_id)
    content = _validate_text_encoding(payload.content or "", "comment.content").strip()
    if not content:
        err.api_error(400, err.E_HTTP, "comment_content_required")
    data = {
        "comment_id": f"cmt_{uuid.uuid4().hex[:12]}",
        "resource_type": "algorithm",
        "resource_id": algorithm_id,
        "author_id": _username_of(current_user),
        "content": content,
        "created_at": time.time(),
    }
    _save_resource_comment(r, "algorithm", algorithm_id, data)
    return ResourceCommentOut(**data)


@app.delete("/community/algorithms/{algorithm_id}/comments/{comment_id}")
def delete_algorithm_comment(algorithm_id: str, comment_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    alg = load_algorithm(r, algorithm_id)
    if not alg:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    _assert_community_resource_visible(alg, "algorithm", algorithm_id)
    comment = _load_resource_comment(r, "algorithm", algorithm_id, comment_id)
    if not comment:
        err.api_error(404, err.E_HTTP, "comment_not_found", algorithm_id=algorithm_id, comment_id=comment_id)
    if str(comment.get("author_id") or "") != _username_of(current_user):
        err.api_error(403, err.E_HTTP, "forbidden_access")
    _delete_resource_comment(r, "algorithm", algorithm_id, comment_id)
    return {"ok": True}


@app.post("/community/reports", response_model=ReportOut)
def create_report(payload: ReportCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    target_type = str(payload.target_type or "").strip().lower()
    target_id = str(payload.target_id or "").strip()
    resource_type = str(payload.resource_type or "").strip().lower() or None
    resource_id = str(payload.resource_id or "").strip() or None
    reason = _validate_text_encoding(payload.reason or "", "report.reason").strip()
    if target_type not in {"algorithm", "dataset", "comment"}:
        err.api_error(400, err.E_HTTP, "invalid_target_type")
    if not target_id:
        err.api_error(400, err.E_HTTP, "target_id_required")
    if not reason:
        err.api_error(400, err.E_HTTP, "report_reason_required")

    if target_type == "algorithm":
        alg = load_algorithm(r, target_id)
        if not alg:
            err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=target_id)
        _assert_community_resource_visible(alg, "algorithm", target_id)
    elif target_type == "dataset":
        ds = load_dataset(r, target_id)
        if not ds:
            err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=target_id)
        _assert_community_resource_visible(ds, "dataset", target_id)
    else:
        if resource_type not in {"algorithm", "dataset"} or not resource_id:
            err.api_error(400, err.E_HTTP, "comment_resource_required")
        resource = load_algorithm(r, resource_id) if resource_type == "algorithm" else load_dataset(r, resource_id)
        if not resource:
            err.api_error(404, err.E_HTTP, "resource_not_found", resource_type=resource_type, resource_id=resource_id)
        _assert_community_resource_visible(resource, resource_type, resource_id)
        comment = _load_resource_comment(r, resource_type, resource_id, target_id)
        if not comment:
            err.api_error(404, err.E_HTTP, "comment_not_found", resource_type=resource_type, resource_id=resource_id, comment_id=target_id)
        reporter_id = _username_of(current_user)
        if str(comment.get("author_id") or "") == reporter_id:
            err.api_error(400, err.E_HTTP, "cannot_report_own_comment")

    reporter_id = _username_of(current_user)
    for item in _list_reports(r):
        if str(item.get("status") or "pending") != "pending":
            continue
        if str(item.get("reporter_id") or "") != reporter_id:
            continue
        if str(item.get("target_type") or "") != target_type:
            continue
        if str(item.get("target_id") or "") != target_id:
            continue
        if str(item.get("resource_type") or "") != str(resource_type or ""):
            continue
        if str(item.get("resource_id") or "") != str(resource_id or ""):
            continue
        err.api_error(409, err.E_HTTP, "report_already_exists")

    data = {
        "report_id": f"rpt_{uuid.uuid4().hex[:12]}",
        "target_type": target_type,
        "target_id": target_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "reporter_id": reporter_id,
        "reason": reason,
        "status": "pending",
        "resolution": "",
        "created_at": time.time(),
        "resolved_at": None,
        "resolved_by": None,
    }
    _save_report(r, data["report_id"], data)
    return ReportOut(**data)


@app.get("/admin/community/algorithms", response_model=list[AlgorithmOut])
def admin_list_community_algorithms(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    items = list_algorithms(r, limit=5000, owner_id=None, include_public=True) or []
    out = []
    for item in items:
      owner_id = str(item.get("owner_id") or "system")
      visibility = str(item.get("visibility") or "private").lower()
      if owner_id == "system":
          continue
      if not _is_algorithm_active(item):
          continue
      if visibility != "public":
          continue
      out.append(AlgorithmOut(**item))
    return out


@app.get("/admin/community/algorithms/{algorithm_id}")
def admin_get_community_algorithm_detail(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    return AlgorithmOut(**cur).model_dump()


@app.get("/admin/community/datasets", response_model=list[DatasetOut])
def admin_list_community_datasets(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    items = list_datasets(r, limit=5000, owner_id=None, include_public=True) or []
    out = []
    for item in items:
      owner_id = str(item.get("owner_id") or "system")
      visibility = str(item.get("visibility") or "private").lower()
      if owner_id == "system":
          continue
      if visibility != "public":
          continue
      out.append(DatasetOut(**item))
    return out


@app.get("/admin/community/datasets/{dataset_id}")
def admin_get_community_dataset_detail(dataset_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    return {
        **DatasetOut(**cur).model_dump(),
        "storage_path": str(_dataset_dir_from_record(cur)),
    }


@app.get("/admin/comments", response_model=list[ResourceCommentOut])
def admin_list_comments(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    return [ResourceCommentOut(**item) for item in _list_all_comments(r)]


@app.post("/admin/community/algorithms/{algorithm_id}/takedown", response_model=AlgorithmOut)
def admin_takedown_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    if str(cur.get("owner_id") or "system") == "system":
        err.api_error(403, err.E_HTTP, "cannot_takedown_system_algorithm", algorithm_id=algorithm_id)
    source_owner = str(cur.get("owner_id") or "").strip()
    source_name = str(cur.get("name") or algorithm_id).strip() or algorithm_id
    cur["visibility"] = "private"
    cur["allow_use"] = False
    cur["allow_download"] = False
    save_algorithm(r, algorithm_id, cur)
    for item in _list_all_algorithm_records(r):
        if str(item.get("owner_id") or "").strip() in {"", "system", source_owner}:
            continue
        if str(item.get("source_algorithm_id") or "") != algorithm_id:
            continue
        if str(item.get("source_owner_id") or "") != source_owner:
            continue
        affected_user = str(item.get("owner_id") or "").strip()
        _delete_algorithm_record_with_related_state(r, item)
        if affected_user:
            _create_notice(
                r,
                affected_user,
                "社区算法已下架",
                f"你下载的社区算法“{source_name}”已被管理员下架，副本已从你的算法库中移除。",
                kind="warning",
            )
    return AlgorithmOut(**cur)


@app.post("/admin/community/algorithms/{algorithm_id}/promote", response_model=AlgorithmOut)
def admin_promote_community_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    source = load_algorithm(r, algorithm_id)
    if not source:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)

    source_owner = str(source.get("owner_id") or "system").strip() or "system"
    visibility = str(source.get("visibility") or "private").lower()
    if source_owner == "system":
        err.api_error(409, err.E_HTTP, "algorithm_already_platform_owned", algorithm_id=algorithm_id)
    if visibility != "public":
        err.api_error(403, err.E_HTTP, "algorithm_not_public", algorithm_id=algorithm_id)

    for existing in list_algorithms(r, limit=5000, owner_id="system", include_public=True) or []:
        if (
            str(existing.get("owner_id") or "") == "system"
            and str(existing.get("source_algorithm_id") or "") == algorithm_id
            and str(existing.get("source_owner_id") or "") == source_owner
        ):
            if _is_algorithm_active(existing):
                return AlgorithmOut(**existing)
            restored = dict(existing)
            restored["task"] = source.get("task")
            restored["name"] = str(source.get("name") or algorithm_id).strip() or algorithm_id
            restored["impl"] = source.get("impl")
            restored["version"] = source.get("version")
            restored["description"] = source.get("description")
            restored["default_params"] = dict(source.get("default_params") or {})
            restored["param_presets"] = dict(source.get("param_presets") or {})
            restored["visibility"] = "public"
            restored["allow_use"] = True
            restored["allow_download"] = True
            restored["is_active"] = True
            restored["updated_at"] = time.time()
            save_algorithm(r, str(existing.get("algorithm_id") or ""), restored)
            return AlgorithmOut(**restored)

    promoted = dict(source)
    promoted["algorithm_id"] = _make_platform_algorithm_id(r, algorithm_id)
    promoted["owner_id"] = "system"
    promoted["name"] = _make_unique_algorithm_name(r, str(source.get("name") or algorithm_id).strip() or algorithm_id)
    promoted["created_at"] = time.time()
    promoted["visibility"] = "public"
    promoted["allow_use"] = True
    promoted["allow_download"] = True
    promoted["is_active"] = True
    promoted["source_algorithm_id"] = algorithm_id
    promoted["source_owner_id"] = source_owner
    save_algorithm(r, promoted["algorithm_id"], promoted)

    if source_owner:
        _create_notice(
            r,
            source_owner,
            "社区算法已被平台收录",
            f"你上传的社区算法“{str(source.get('name') or algorithm_id).strip() or algorithm_id}”已被管理员收录进平台标准算法库。",
            kind="success",
        )

    return AlgorithmOut(**promoted)


@app.post("/admin/community/datasets/{dataset_id}/takedown", response_model=DatasetOut)
def admin_takedown_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    if str(cur.get("owner_id") or "system") == "system":
        err.api_error(403, err.E_HTTP, "cannot_takedown_system_dataset", dataset_id=dataset_id)
    source_owner = str(cur.get("owner_id") or "").strip()
    source_name = str(cur.get("name") or dataset_id).strip() or dataset_id
    cur["visibility"] = "private"
    cur["allow_use"] = False
    cur["allow_download"] = False
    save_dataset(r, dataset_id, cur)
    for item in _list_all_dataset_records(r):
        item_owner = str(item.get("owner_id") or "").strip()
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        if item_owner in {"", "system", source_owner}:
            continue
        if str(meta.get("downloaded_from_dataset_id") or "") != dataset_id:
            continue
        if str(meta.get("downloaded_from_owner_id") or "") != source_owner:
            continue
        deleted_disk = _delete_dataset_record_with_related_state(r, item, delete_disk=True)
        if item_owner:
            suffix = "，对应磁盘文件也已清理。" if deleted_disk else "。"
            _create_notice(
                r,
                item_owner,
                "社区数据集已下架",
                f"你下载的社区数据集“{source_name}”已被管理员下架，副本已从你的数据集库中移除{suffix}",
                kind="warning",
            )
    return DatasetOut(**cur)


@app.delete("/admin/comments/{resource_type}/{resource_id}/{comment_id}")
def admin_delete_comment(resource_type: str, resource_id: str, comment_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    resource_type = str(resource_type or "").strip().lower()
    if resource_type not in {"algorithm", "dataset"}:
        err.api_error(400, err.E_HTTP, "invalid_resource_type")
    r = make_redis()
    comment = _load_resource_comment(r, resource_type, resource_id, comment_id)
    if not comment:
        err.api_error(404, err.E_HTTP, "comment_not_found", resource_type=resource_type, resource_id=resource_id, comment_id=comment_id)
    _delete_resource_comment(r, resource_type, resource_id, comment_id)
    return {"ok": True}


@app.get("/admin/reports", response_model=list[ReportOut])
def admin_list_reports(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    return [ReportOut(**item) for item in _list_reports(r)]


@app.post("/admin/reports/{report_id}/resolve", response_model=ReportOut)
def admin_resolve_report(report_id: str, payload: ReportResolve, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    r = make_redis()
    cur = _load_report(r, report_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "report_not_found", report_id=report_id)
    status = str(payload.status or "resolved").strip().lower()
    if status not in {"resolved", "rejected"}:
        err.api_error(400, err.E_HTTP, "invalid_report_status")
    cur["status"] = status
    cur["resolution"] = _validate_text_encoding(payload.resolution or "", "report.resolution").strip()
    cur["resolved_at"] = time.time()
    cur["resolved_by"] = _username_of(current_user)
    _save_report(r, report_id, cur)
    reporter_id = str(cur.get("reporter_id") or "").strip()
    if reporter_id:
        content = "你提交的举报已由管理员处理。"
        if status == "rejected":
            content = "你提交的举报已由管理员驳回。"
        if cur["resolution"]:
            content = f"{content} 处理结果：{cur['resolution']}"
        _create_notice(r, reporter_id, "举报已处理", content, kind="info")
    return ReportOut(**cur)


@app.post("/admin/reports/clear")
def admin_clear_reports(
    status: str = Query("handled"),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    wanted = str(status or "handled").strip().lower()
    if wanted not in {"handled", "all"}:
        err.api_error(400, err.E_HTTP, "invalid_clear_scope")
    r = make_redis()
    deleted = 0
    for item in _list_reports(r):
        item_status = str(item.get("status") or "pending").strip().lower()
        if wanted == "handled" and item_status == "pending":
            continue
        _delete_report(r, str(item.get("report_id") or ""))
        deleted += 1
    return {"ok": True, "deleted": deleted, "status": wanted}


@app.post("/algorithms/reset_user")
def reset_user_algorithms(current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    username = _username_of(current_user)
    removed = 0
    for x in list_algorithms(r, limit=5000, owner_id=username):
        aid = str(x.get("algorithm_id") or "")
        if not aid or aid in BUILTIN_ALGORITHM_IDS:
            continue
        if str(x.get("owner_id") or "") != username:
            continue
        delete_algorithm(r, aid)
        removed += 1
    _ensure_catalog_defaults(r)
    return {"ok": True, "removed": removed}


@app.get("/presets")
def get_presets(limit: int = 200, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    owner_id = current_user["username"] if current_user else None
    items = list_presets(r, limit=limit, owner_id=owner_id) or []
    return [PresetOut(**x).model_dump() for x in items]


@app.get("/presets/{preset_id}", response_model=PresetOut)
def get_preset(preset_id: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    cur = load_preset(r, preset_id)
    if not cur:
        err.api_error(404, err.E_PRESET_NOT_FOUND, "preset_not_found", preset_id=preset_id)
    _assert_resource_access(cur, current_user, allow_system=True)
    return PresetOut(**cur)


@app.post("/presets", response_model=PresetOut)
def create_preset(payload: PresetCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    preset_id = (payload.preset_id or "").strip() or f"pre_{uuid.uuid4().hex[:10]}"
    if load_preset(r, preset_id):
        err.api_error(409, err.E_PRESET_ID_EXISTS, "preset_id_exists", preset_id=preset_id)
    created = time.time()
    owner_id = current_user["username"]
    data = {
        "preset_id": preset_id,
        "name": _validate_text_encoding(payload.name, "preset.name"),
        "task_type": payload.task_type,
        "dataset_id": payload.dataset_id,
        "algorithm_id": payload.algorithm_id,
        "metrics": payload.metrics or [],
        "params": payload.params or {},
        "owner_id": owner_id,
        "created_at": created,
        "updated_at": created,
    }
    save_preset(r, preset_id, data)
    return PresetOut(**data)


@app.patch("/presets/{preset_id}", response_model=PresetOut)
def patch_preset(preset_id: str, payload: PresetPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    cur = load_preset(r, preset_id)
    if not cur:
        err.api_error(404, err.E_PRESET_NOT_FOUND, "preset_not_found", preset_id=preset_id)
    
    _assert_resource_access(cur, current_user, allow_system=False)
        
    if payload.name is not None:
        cur["name"] = _validate_text_encoding(payload.name, "preset.name")
    if payload.task_type is not None:
        cur["task_type"] = payload.task_type
    if payload.dataset_id is not None:
        cur["dataset_id"] = payload.dataset_id
    if payload.algorithm_id is not None:
        cur["algorithm_id"] = payload.algorithm_id
    if payload.metrics is not None:
        cur["metrics"] = payload.metrics
    if payload.params is not None:
        cur["params"] = payload.params
    cur["updated_at"] = time.time()
    save_preset(r, preset_id, cur)
    return PresetOut(**cur)


@app.delete("/presets/{preset_id}")
def remove_preset(preset_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    cur = load_preset(r, preset_id)
    if not cur:
        err.api_error(404, err.E_PRESET_NOT_FOUND, "preset_not_found", preset_id=preset_id)
    
    _assert_resource_access(cur, current_user, allow_system=False)
        
    delete_preset(r, preset_id)
    return {"ok": True, "preset_id": preset_id}


@app.post("/recommend/fast-select", response_model=FastSelectResponse)
def recommend_fast_select(payload: FastSelectRequest, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    username = _username_of(current_user)
    is_admin = _normalize_user_role(current_user) == "admin"
    task_type = (payload.task_type or "").strip().lower()
    dataset_id = (payload.dataset_id or "").strip()
    if task_type not in TASK_LABEL_BY_TYPE:
        err.api_error(400, err.E_BAD_TASK_TYPE, "bad_task_type", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
    aggregate_dataset_count = 0
    if not dataset_id:
        if not is_admin:
            err.api_error(400, err.E_DATASET_ID_REQUIRED, "dataset_id_required")
        meta, pair_count, aggregate_dataset_count = _aggregate_dataset_meta_for_task(r, task_type, current_user)
        if pair_count <= 0:
            err.api_error(
                409,
                err.E_DATASET_NO_PAIR,
                "dataset_no_pair_for_task",
                task_type=task_type,
                dataset_id="",
                pair_count=pair_count,
            )
    else:
        ds = load_dataset(r, dataset_id)
        if not ds:
            err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
        _assert_resource_access(ds, current_user, allow_system=True)
        meta = ds.get("meta") if isinstance(ds.get("meta"), dict) else {}
        pairs_map = meta.get("pairs_by_task") if isinstance(meta.get("pairs_by_task"), dict) else {}
        pair_count = int(pairs_map.get(task_type) or 0)
        if pair_count <= 0:
            err.api_error(
                409,
                err.E_DATASET_NO_PAIR,
                "dataset_no_pair_for_task",
                task_type=task_type,
                dataset_id=dataset_id,
                pair_count=pair_count,
            )

    task_label = TASK_LABEL_BY_TYPE.get(task_type, "")
    if payload.candidate_algorithm_ids:
        candidate_ids = []
        for x in payload.candidate_algorithm_ids:
            aid = str(x or "").strip()
            if aid:
                candidate_ids.append(aid)
    else:
        all_algs = list_algorithms(r, limit=2000, owner_id=(username or None)) or []
        candidate_ids = [str(x.get("algorithm_id") or "") for x in all_algs if str((x.get("task") or "")).strip() == task_label]

    def _normalize_effective_params(params: dict | None) -> dict:
        src = params if isinstance(params, dict) else {}
        ignore = {"batch_id", "batch_name", "source", "fast_top_k", "fast_alpha", "metrics", "param_scheme", "user_scheme_name"}
        out = {}
        for k in sorted(src.keys()):
            if k in ignore:
                continue
            out[k] = src.get(k)
        return out

    def _scheme_base_name(name: str) -> str:
        n = str(name or "").strip()
        if n.endswith("）"):
            i = n.rfind("（")
            if i > 0:
                return n[:i].strip()
        if n.endswith(")"):
            i = n.rfind("(")
            if i > 0:
                return n[:i].strip()
        return n

    def _algorithm_family_tokens(alg: dict | None) -> set[str]:
        if not isinstance(alg, dict):
            return set()
        tokens: set[str] = set()
        for raw in (
            _scheme_base_name(str(alg.get("name") or "")),
            str(alg.get("impl") or ""),
            str(alg.get("algorithm_id") or ""),
        ):
            text = str(raw or "").strip().lower()
            if not text:
                continue
            tokens.add(text)
            plain = "".join(ch for ch in text if ch.isalnum())
            if plain:
                tokens.add(plain)
        alias_map = {
            "fastnlmeans": {"fastnlmeans", "dncnn"},
            "dncnn": {"fastnlmeans", "dncnn"},
            "bilateral": {"bilateral"},
            "gaussian": {"gaussian", "videogaussian"},
            "median": {"median", "videomedian"},
            "clahe": {"clahe"},
            "gamma": {"gamma"},
            "dcp": {"dcp", "darkchannel"},
            "unsharpmask": {"unsharpmask", "unsharp"},
            "laplaciansharpen": {"laplaciansharpen", "laplacian"},
            "bicubic": {"bicubic", "videobicubic"},
            "lanczos": {"lanczos", "videolanczos"},
            "nearest": {"nearest", "videonearest"},
            "linear": {"linear", "videolinear"},
            "gammaclahehybrid": {"gammaclahehybrid", "hybrid"},
        }
        expanded = set(tokens)
        for token in list(tokens):
            for key, aliases in alias_map.items():
                if key in token or any(alias in token for alias in aliases):
                    expanded.update(aliases)
                    expanded.add(key)
        return expanded

    uniq = []
    seen = set()
    for aid in candidate_ids:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        uniq.append(aid)
    candidate_ids = uniq
    if not candidate_ids:
        err.api_error(409, err.E_TASK_NOT_SUPPORTED, "no_candidate_algorithms", task_type=task_type, task_label=task_label)

    valid_ids = []
    alg_by_id: dict[str, dict] = {}
    candidate_defaults: dict[str, dict] = {}
    for aid in candidate_ids:
        alg = load_algorithm(r, aid)
        if not alg:
            err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=aid)
        alg_owner = str((alg.get("owner_id") or "system")).strip() or "system"
        alg_visibility = str((alg.get("visibility") or "private")).lower()
        if is_admin and alg_owner != "system":
            if alg_visibility != "public":
                err.api_error(403, err.E_HTTP, "algorithm_not_public", algorithm_id=aid)
        else:
            _assert_resource_access(alg, current_user, allow_system=True)
        if str((alg.get("task") or "")).strip() != task_label:
            err.api_error(
                409,
                err.E_ALGORITHM_TASK_MISMATCH,
                "algorithm_task_mismatch",
                algorithm_id=aid,
                algorithm_task=(alg.get("task") or ""),
                task_type=task_type,
                task_label=task_label,
            )
        valid_ids.append(aid)
        alg_by_id[aid] = alg
        candidate_defaults[aid] = _normalize_effective_params(alg.get("default_params") if isinstance(alg.get("default_params"), dict) else {})

    target_context = build_context_vector(task_type=task_type, dataset_meta=meta)
    alpha = float(payload.alpha if payload.alpha is not None else 0.35)
    alpha = max(0.0, min(alpha, 2.0))
    lambda_reg = float(payload.lambda_reg if payload.lambda_reg is not None else 1.0)
    lambda_reg = max(0.05, min(lambda_reg, 50.0))
    recency_half_life_hours = float(payload.recency_half_life_hours if payload.recency_half_life_hours is not None else 72.0)
    recency_half_life_hours = max(1.0, min(recency_half_life_hours, 24.0 * 60.0))
    cold_start_bonus = float(payload.cold_start_bonus if payload.cold_start_bonus is not None else 0.08)
    cold_start_bonus = max(0.0, min(cold_start_bonus, 0.5))
    low_support_penalty = float(payload.low_support_penalty if payload.low_support_penalty is not None else 0.06)
    low_support_penalty = max(0.0, min(low_support_penalty, 0.5))
    min_support = int(payload.min_support if payload.min_support is not None else 3)
    min_support = max(1, min(min_support, 50))
    cfg = FastSelectConfig(
        alpha=alpha,
        lambda_reg=lambda_reg,
        recency_half_life_hours=recency_half_life_hours,
        cold_start_bonus=cold_start_bonus,
        low_support_penalty=low_support_penalty,
        min_support=min_support,
    )
    model = load_online_model(r, task_type)
    historical_done_count = 0
    if (not is_admin) and model and int(model.get("feature_dim") or 0) == int(target_context.shape[0]):
        arm_stats = fast_select_algorithms_online(
            task_type=task_type,
            candidate_algorithm_ids=valid_ids,
            target_context=target_context,
            model=model,
            config=cfg,
        )
        arms = model.get("arms") if isinstance(model.get("arms"), dict) else {}
        historical_done_count = int(sum(int((v or {}).get("sample_count") or 0) for v in arms.values() if isinstance(v, dict)))
    else:
        runs = (_list_all_runs(r, limit=5000) if is_admin else list_runs(r, limit=5000, owner_id=(username or None))) or []
        run_alg_cache: dict[str, dict] = {}
        augmented_runs = list(runs)
        for run in runs:
            if str(run.get("task_type") or "") != task_type:
                continue
            if str(run.get("status") or "").lower() != "done":
                continue
            run_alg_id = str(run.get("algorithm_id") or "")
            if not run_alg_id:
                continue
            if run_alg_id not in run_alg_cache:
                run_alg_cache[run_alg_id] = load_algorithm(r, run_alg_id) or {}
            run_alg = run_alg_cache.get(run_alg_id) or {}
            run_base = _scheme_base_name(str(run_alg.get("name") or ""))
            run_family = _algorithm_family_tokens(run_alg)
            run_eff = _normalize_effective_params(run.get("params") if isinstance(run.get("params"), dict) else {})
            for aid in valid_ids:
                if aid == run_alg_id:
                    continue
                cand_alg = alg_by_id.get(aid) or {}
                cand_base = _scheme_base_name(str(cand_alg.get("name") or ""))
                cand_family = _algorithm_family_tokens(cand_alg)
                cand_eff = candidate_defaults.get(aid) or {}
                same_base = bool(cand_base and run_base and cand_base == run_base)
                same_family = bool(cand_family and run_family and (cand_family & run_family))
                if not same_base and not same_family:
                    continue
                if run_eff and cand_eff and run_eff != cand_eff:
                    continue
                shadow = dict(run)
                shadow["algorithm_id"] = aid
                shadow["_shadow_reused"] = True
                shadow["_shadow_source_algorithm_id"] = run_alg_id
                augmented_runs.append(shadow)
        arm_stats = fast_select_algorithms(
            task_type=task_type,
            candidate_algorithm_ids=valid_ids,
            historical_runs=augmented_runs,
            target_context=target_context,
            config=cfg,
        )
        historical_done_count = len([x for x in runs if str(x.get("task_type") or "") == task_type and str(x.get("status") or "").lower() == "done"])
        bootstrap_online_model_from_runs(r, task_type=task_type, historical_runs=runs, config=cfg)

    top_k = int(payload.top_k if payload.top_k is not None else 3)
    if top_k < 1:
        top_k = 1
    if top_k > len(arm_stats):
        top_k = len(arm_stats)

    recs = [
        FastSelectItem(
            algorithm_id=x.algorithm_id,
            score=x.score,
            expected_reward=x.expected_reward,
            mean_reward=x.mean_reward,
            uncertainty=x.uncertainty,
            exploration_bonus=x.exploration_bonus,
            cold_start_bonus=x.cold_start_bonus,
            reliability=x.reliability,
            sample_count=x.sample_count,
            direct_sample_count=x.direct_sample_count,
            shadow_sample_count=x.shadow_sample_count,
        )
        for x in arm_stats[:top_k]
    ]

    context = {
        "pair_count": pair_count,
        "supported_tasks": meta.get("supported_task_types") if isinstance(meta.get("supported_task_types"), list) else [],
        "counts_by_dir": meta.get("counts_by_dir") if isinstance(meta.get("counts_by_dir"), dict) else {},
        "feature_dim": int(target_context.shape[0]),
        "candidate_count": len(valid_ids),
        "historical_run_count": historical_done_count,
        "alpha": alpha,
        "lambda_reg": lambda_reg,
        "recency_half_life_hours": recency_half_life_hours,
        "cold_start_bonus": cold_start_bonus,
        "low_support_penalty": low_support_penalty,
        "min_support": min_support,
        "online_model": bool(model),
        "dataset_mode": "single" if dataset_id else "aggregate",
        "aggregate_dataset_count": aggregate_dataset_count,
    }

    return FastSelectResponse(
        task_type=task_type,
        dataset_id=dataset_id,
        top_k=top_k,
        reward_formula="expected + alpha*uncertainty + cold_start_bonus/sqrt(n+1) - low_support_penalty*(1-reliability)",
        context=context,
        recommendations=recs,
    )


@app.post("/runs", response_model=RunOut)
def create_run(payload: RunCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    task_type = (payload.task_type or "").strip().lower()
    dataset_id = (payload.dataset_id or "").strip()
    algorithm_id = (payload.algorithm_id or "").strip()
    owner_id = current_user["username"]
    if task_type not in TASK_LABEL_BY_TYPE:
        err.api_error(400, err.E_BAD_TASK_TYPE, "\u4e0d\u652f\u6301\u7684\u4efb\u52a1\u7c7b\u578b", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
    if not dataset_id:
        err.api_error(400, err.E_DATASET_ID_REQUIRED, "\u7f3a\u5c11 dataset_id")
    if not algorithm_id:
        err.api_error(400, err.E_ALGORITHM_ID_REQUIRED, "\u7f3a\u5c11 algorithm_id")

    ds = load_dataset(r, dataset_id)
    if not ds:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "\u6570\u636e\u96c6\u4e0d\u5b58\u5728", dataset_id=dataset_id)
    _assert_resource_access(ds, current_user, allow_system=True)
    alg = load_algorithm(r, algorithm_id)
    if not alg:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "\u7b97\u6cd5\u4e0d\u5b58\u5728", algorithm_id=algorithm_id)
    _assert_resource_access(alg, current_user, allow_system=True)

    expected_task = TASK_LABEL_BY_TYPE.get(task_type, "")
    if expected_task and (alg.get("task") or "").strip() != expected_task:
        err.api_error(
            409,
            err.E_ALGORITHM_TASK_MISMATCH,
            "\u7b97\u6cd5\u4efb\u52a1\u4e0e\u4efb\u52a1\u7c7b\u578b\u4e0d\u5339\u914d",
            task_type=task_type,
            task_label=TASK_LABEL_BY_TYPE.get(task_type, ""),
            expected_algorithm_task=expected_task,
            algorithm_task=(alg.get("task") or "").strip(),
        )

    from .vision.dataset_access import count_paired_images, count_paired_videos

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 确保数据目录存在
    data_root.mkdir(parents=True, exist_ok=True)
    input_dir_by_task = {
        "dehaze": "hazy",
        "denoise": "noisy",
        "deblur": "blur",
        "sr": "lr",
        "lowlight": "dark",
        "video_denoise": "noisy",
        "video_sr": "lr",
    }
    input_dirname = input_dir_by_task.get(task_type)
    if not input_dirname:
        err.api_error(400, err.E_BAD_TASK_TYPE, "\u4e0d\u652f\u6301\u7684\u4efb\u52a1\u7c7b\u578b", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
    dataset_owner_id, dataset_storage_path = _dataset_runtime_owner_and_storage(ds, owner_id)
    if task_type.startswith("video_"):
        pair_count = count_paired_videos(
            data_root=data_root,
            owner_id=dataset_owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname="gt",
            storage_path=dataset_storage_path,
        )
    else:
        pair_count = count_paired_images(
            data_root=data_root,
            owner_id=dataset_owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname="gt",
            storage_path=dataset_storage_path,
        )
    if pair_count <= 0:
        err.api_error(
            409,
            err.E_DATASET_NO_PAIR,
            "\u5f53\u524d\u4efb\u52a1\u65e0\u53ef\u7528\u914d\u5bf9\uff0c\u8bf7\u68c0\u67e5\u8f93\u5165\u76ee\u5f55\u4e0e gt/ \u540c\u540d\u6587\u4ef6\u5e76\u91cd\u65b0\u626b\u63cf",
            task_type=task_type,
            task_label=TASK_LABEL_BY_TYPE.get(task_type, ""),
            dataset_id=dataset_id,
            expected_dirs=[input_dirname, "gt"],
            pair_count=pair_count,
        )

    run_id = uuid.uuid4().hex[:12]
    created = time.time()

    run = {
        "run_id": run_id,
        "task_type": task_type,
        "dataset_id": dataset_id,
        "algorithm_id": algorithm_id,
        "owner_id": owner_id,
        "params": payload.params,
        "strict_validate": bool(getattr(payload, "strict_validate", False)),
        "samples": [],
        "cancel_requested": False,

        "status": "queued",
        "created_at": created,
        "started_at": None,
        "finished_at": None,
        "elapsed": None,
        "metrics": {},
        "error": None,
        "error_code": None,
        "error_detail": None,
        "record": {
            "dataset": {
                "dataset_id": dataset_id,
                "owner_id": dataset_owner_id,
                "storage_path": dataset_storage_path,
                "source_owner_id": ds.get("source_owner_id"),
                "source_dataset_id": ds.get("source_dataset_id"),
            }
        },
    }
    save_run(r, run_id, run)

    execute_run.apply_async((run_id,), task_id=run_id)

    return RunOut(**run)


@app.get("/runs")
def get_runs(
    limit: int = 200,
    status: str | None = Query(None, description="queued|running|canceling|canceled|done|failed"),
    task_type: str | None = Query(None, description="denoise/deblur/dehaze/sr/lowlight/video_denoise/video_sr"),
    dataset_id: str | None = Query(None),
    algorithm_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user)
):
    r = make_redis()
    owner_id = _username_of(current_user) or None
    runs = list_runs(r, limit=limit, owner_id=owner_id)

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

    runs = [x for x in (runs or []) if ok(x)]
    return [_sanitize_run_for_api(x) for x in runs]

@app.get("/runs/export")
def export_runs(
    format: str = Query("csv", description="csv|xlsx"),
    status: str | None = Query(None, description="queued|running|canceling|canceled|done|failed"),
    task_type: str | None = Query(None, description="denoise/deblur/dehaze/sr/lowlight/video_denoise/video_sr"),
    dataset_id: str | None = Query(None),
    algorithm_id: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Export runs as CSV/XLSX.
    """
    fmt = (format or "").lower().strip()
    if fmt not in ("csv", "xlsx"):
        err.api_error(400, err.E_EXPORT_FORMAT, "format_must_be_csv_or_xlsx", format=fmt)

    r = make_redis()
    owner_id = _username_of(current_user) or None
    runs = list_runs(r, limit=limit, owner_id=owner_id)

    # ===== 筛选当前导出范围 =====
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

    # ===== 展平 params / samples 字段 =====
    headers = [
        "run_id",
        "task_type",
        "task_label",
        "dataset_id",
        "dataset_name",
        "algorithm_id",
        "algorithm_name",
        "algorithm_task",
        "batch_id",
        "batch_name",
        "param_scheme",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "elapsed",
        "strict_validate",
        "data_mode",
        "input_dir",
        "pair_total",
        "pair_used",
        "read_ok",
        "read_fail",
        "algo_elapsed_mean",
        "algo_elapsed_sum",
        "metric_elapsed_mean",
        "metric_elapsed_sum",
        "metric_psnr_ssim_elapsed_mean",
        "metric_psnr_ssim_elapsed_sum",
        "metric_niqe_elapsed_mean",
        "metric_niqe_elapsed_sum",
        "PSNR",
        "SSIM",
        "NIQE",
        "error_code",
        "error",
        "error_detail_json",
        "params_json",
        "samples_json",
        "record_json",
    ]

    def to_row(x: dict) -> dict:
        m = x.get("metrics") or {}
        params = dict(x.get("params") or {})
        params.pop("niqe_fallback", None)
        samples = x.get("samples") or []
        record = x.get("record") if isinstance(x.get("record"), dict) else {}
        ds = record.get("dataset") if isinstance(record.get("dataset"), dict) else {}
        alg = record.get("algorithm") if isinstance(record.get("algorithm"), dict) else {}
        batch = record.get("batch") if isinstance(record.get("batch"), dict) else {}
        task_t = x.get("task_type")
        return {
            "run_id": x.get("run_id"),
            "task_type": x.get("task_type"),
            "task_label": TASK_LABEL_BY_TYPE.get(str(task_t or ""), ""),
            "dataset_id": x.get("dataset_id"),
            "dataset_name": ds.get("name"),
            "algorithm_id": x.get("algorithm_id"),
            "algorithm_name": alg.get("name"),
            "algorithm_task": alg.get("task"),
            "batch_id": batch.get("batch_id") or params.get("batch_id"),
            "batch_name": batch.get("batch_name") or params.get("batch_name"),
            "param_scheme": batch.get("param_scheme") or params.get("param_scheme"),
            "status": x.get("status"),
            "created_at": x.get("created_at"),
            "started_at": x.get("started_at"),
            "finished_at": x.get("finished_at"),
            "elapsed": x.get("elapsed"),
            "strict_validate": x.get("strict_validate"),
            "data_mode": record.get("data_mode"),
            "input_dir": record.get("input_dir"),
            "pair_total": record.get("pair_total"),
            "pair_used": record.get("pair_used"),
            "read_ok": params.get("read_ok"),
            "read_fail": params.get("read_fail"),
            "algo_elapsed_mean": params.get("algo_elapsed_mean"),
            "algo_elapsed_sum": params.get("algo_elapsed_sum"),
            "metric_elapsed_mean": params.get("metric_elapsed_mean"),
            "metric_elapsed_sum": params.get("metric_elapsed_sum"),
            "metric_psnr_ssim_elapsed_mean": params.get("metric_psnr_ssim_elapsed_mean"),
            "metric_psnr_ssim_elapsed_sum": params.get("metric_psnr_ssim_elapsed_sum"),
            "metric_niqe_elapsed_mean": params.get("metric_niqe_elapsed_mean"),
            "metric_niqe_elapsed_sum": params.get("metric_niqe_elapsed_sum"),
            "PSNR": m.get("PSNR"),
            "SSIM": m.get("SSIM"),
            "NIQE": m.get("NIQE"),
            "error_code": x.get("error_code"),
            "error": x.get("error"),
            "error_detail_json": json.dumps(x.get("error_detail"), ensure_ascii=False),
            "params_json": json.dumps(params, ensure_ascii=False),
            "samples_json": json.dumps(samples, ensure_ascii=False),
            "record_json": json.dumps(record, ensure_ascii=False),
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


@app.post("/runs/clear")
def clear_runs(
    status: str | None = Query("done", description="done|queued|running|failed|all"),
    current_user: dict = Depends(get_current_user),
):
    """
    Clear runs by status (default: done).
    """
    r = make_redis()
    keys = r.keys("run:*")
    username = current_user["username"]

    deleted = 0
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
        except Exception:
            continue
        if str(data.get("owner_id") or "") != username:
            continue

        if status and status != "all":
            if data.get("status") != status:
                continue

        r.delete(k)
        deleted += 1

    return {"ok": True, "deleted": deleted, "status": status}


@app.post("/runs/batch-clear")
def batch_clear_runs(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Clear specific runs by ids for the current user.
    """
    run_ids = payload.get("run_ids") if isinstance(payload, dict) else None
    if not isinstance(run_ids, list) or not run_ids:
        err.api_error(400, err.E_HTTP, "run_ids_required")

    wanted = {str(x).strip() for x in run_ids if str(x).strip()}
    if not wanted:
        err.api_error(400, err.E_HTTP, "run_ids_required")

    r = make_redis()
    username = current_user["username"]
    deleted = 0
    skipped = 0

    for run_id in wanted:
        run = load_run(r, run_id)
        if not run:
            skipped += 1
            continue
        if str(run.get("owner_id") or "") != username:
            skipped += 1
            continue
        if str(run.get("status") or "") in {"queued", "running", "canceling"}:
            skipped += 1
            continue
        r.delete(f"run:{run_id}")
        deleted += 1

    return {"ok": True, "deleted": deleted, "skipped": skipped}



@app.get("/runs/{run_id}")
def get_run(run_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        err.api_error(404, err.E_RUN_NOT_FOUND, "run_not_found", run_id=run_id)
    _assert_resource_access(run, current_user, allow_system=True)
    return _sanitize_run_for_api(run)


@app.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        err.api_error(404, err.E_RUN_NOT_FOUND, "run_not_found", run_id=run_id)
    _assert_resource_access(run, current_user, allow_system=False)

    status = (run.get("status") or "").lower()
    if status in {"done", "failed", "canceled"}:
        return {"ok": True, "run_id": run_id, "status": status}

    cancel_key = f"run_cancel:{run_id}"
    r.set(cancel_key, "1", ex=24 * 3600)
    run["cancel_requested"] = True
    if status == "queued":
        celery_app.control.revoke(run_id)
        finished = time.time()
        run["status"] = "canceled"
        run["finished_at"] = finished
        run["elapsed"] = round(finished - (run.get("started_at") or run.get("created_at") or finished), 3)
        run["error"] = "\u5df2\u53d6\u6d88"
        run["error_code"] = "E_CANCELED"
        run["error_detail"] = {"run_id": run_id, "phase": "queued"}
        save_run(r, run_id, run)
        return {"ok": True, "run_id": run_id, "status": "canceled"}

    run["status"] = "canceling"
    save_run(r, run_id, run)
    celery_app.control.revoke(run_id, terminate=False)
    return {"ok": True, "run_id": run_id, "status": "canceling"}
