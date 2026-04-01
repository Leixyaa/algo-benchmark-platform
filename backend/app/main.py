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

from datetime import datetime
from pathlib import Path

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
    DatasetImportZip,
    AlgorithmCreate,
    AlgorithmOut,
    AlgorithmPatch,
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

import cv2


app = FastAPI(title="Algo Eval Platform API", version="0.1.0")

# --- 用户系统 (User System) ---

@app.post("/register", response_model=UserOut)
def register(payload: UserCreate):
    r = make_redis()
    username = payload.username.strip()
    if not username:
        err.api_error(400, err.E_HTTP, "username_required")
    if load_user(r, username):
        err.api_error(409, err.E_HTTP, "user_already_exists")
    
    user_data = {
        "username": username,
        "hashed_password": get_password_hash(payload.password),
        "created_at": time.time(),
    }
    save_user(r, username, user_data)
    return UserOut(**user_data)


@app.post("/token", response_model=Token)
@app.post("/login", response_model=Token)
def login(payload: UserCreate):
    r = make_redis()
    user = load_user(r, payload.username)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        err.api_error(401, err.E_HTTP, "invalid_credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"]
    }


@app.get("/me", response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)

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
    demo_ds = {
        "dataset_id": demo_ds_id,
        "name": "Demo-样例数据集",
        "type": "图像",
        "size": "10 张",
        "owner_id": "system",
        "created_at": created,
        "meta": {},
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
        if need_patch:
            if not isinstance(cur_ds.get("meta"), dict):
                cur_ds["meta"] = {}
            cur_ds["owner_id"] = "system"
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
        for k in ("task", "name", "impl", "version"):
            if cur.get(k) != x[k]:
                cur[k] = x[k]
                need_patch = True
        if cur.get("default_params") != x.get("default_params"):
            cur["default_params"] = dict(x.get("default_params") or {})
            need_patch = True
        if cur.get("param_presets") != x.get("param_presets"):
            cur["param_presets"] = dict(x.get("param_presets") or {})
            need_patch = True
        if str(cur.get("owner_id") or "") != "system":
            cur["owner_id"] = "system"
            need_patch = True
        if need_patch:
            if not isinstance(cur.get("created_at"), (int, float)):
                cur["created_at"] = created
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


def _username_of(current_user: Optional[dict]) -> str:
    if not isinstance(current_user, dict):
        return ""
    return str(current_user.get("username") or "").strip()


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


def _assert_pinned_user(current_user: dict) -> None:
    if _username_of(current_user) != _PINNED_OWNER_USERNAME:
        err.api_error(403, err.E_HTTP, "forbidden_access")


@app.get("/datasets")
def get_datasets(limit: int = 200, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    # 允许未登录用户获取所有数据集
    owner_id = _username_of(current_user) or None
    return list_datasets(r, limit=limit, owner_id=owner_id)


@app.post("/datasets", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    dataset_id = (payload.dataset_id or "").strip() or f"ds_{uuid.uuid4().hex[:10]}"
    existing_dataset = load_dataset(r, dataset_id)
    owner_id = _username_of(current_user)
    
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
        }
    else:
        # 创建新数据集
        created = time.time()
        data = {
            "dataset_id": dataset_id,
            "name": _validate_text_encoding(payload.name, "dataset.name"),
            "type": _validate_text_encoding(payload.type, "dataset.type"),
            "size": _validate_text_encoding(payload.size, "dataset.size"),
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
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
    if not isinstance(cur.get("meta"), dict):
        cur["meta"] = {}
    save_dataset(r, dataset_id, cur)
    return DatasetOut(**cur)


@app.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
        
    delete_dataset(r, dataset_id)
    return {"ok": True, "dataset_id": dataset_id}


def _get_dataset_version_key(dataset_id: str) -> str:
    return f"dataset:version:{dataset_id}"


def _increment_dataset_version(r, dataset_id: str) -> int:
    version_key = _get_dataset_version_key(dataset_id)
    version = r.incr(version_key)
    return version


def _get_dataset_fs_hash(owner_id: str, dataset_id: str) -> str:
    """计算数据集文件系统的哈希值，用于检测文件变化"""
    data_root = Path(__file__).resolve().parents[1] / "data"
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
    current_fs_hash = _get_dataset_fs_hash(owner_id, dataset_id)
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
        t, size, meta = _scan_dataset_on_disk(data_root, owner_id, dataset_id)
        
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
    
    meta = dict(meta or {})
    meta["inferred_type"] = t
    current_type = str(cur.get("type") or "").strip()
    if not current_type:
        cur["type"] = t
        current_type = str(cur.get("type") or "").strip()
    meta["type_mismatch"] = bool(current_type and current_type != t)
    cur["size"] = _size_by_declared_type(current_type, t, size, meta)
    cur["meta"] = meta
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

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 使用用户独有的目录结构
    user_dir = data_root / owner_id
    # 确保数据目录存在
    user_dir.mkdir(parents=True, exist_ok=True)
    ds_dir = user_dir / dataset_id
    if payload.overwrite and ds_dir.exists():
        shutil.rmtree(ds_dir)
    _safe_extract_zip_bytes(zip_bytes, ds_dir)
    _normalize_dataset_import_layout(ds_dir, overwrite=bool(payload.overwrite))

    t, size, meta = _scan_dataset_on_disk(data_root, owner_id, dataset_id)
    meta = dict(meta or {})
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
    user_dir.mkdir(parents=True, exist_ok=True)
    ds_dir = user_dir / dataset_id
    if overwrite and ds_dir.exists():
        shutil.rmtree(ds_dir)
    _safe_extract_zip_bytes(zip_bytes, ds_dir)
    _normalize_dataset_import_layout(ds_dir, overwrite=overwrite)

    t, size, meta = _scan_dataset_on_disk(data_root, owner_id, dataset_id)
    meta = dict(meta or {})
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
def get_algorithms(limit: int = 500, current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    owner_id = current_user["username"] if current_user else None
    catalog = _builtin_algorithm_catalog()
    defaults_by_id = {x["algorithm_id"]: dict(x.get("default_params") or {}) for x in catalog}
    presets_by_id = {x["algorithm_id"]: dict(x.get("param_presets") or {}) for x in catalog}

    items = list_algorithms(r, limit=limit, owner_id=owner_id) or []
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
        out.append(AlgorithmOut(**x).model_dump())
    return out


@app.post("/algorithms", response_model=AlgorithmOut)
def create_algorithm(payload: AlgorithmCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    algorithm_id = (payload.algorithm_id or "").strip() or f"alg_{uuid.uuid4().hex[:10]}"
    existing_algorithm = load_algorithm(r, algorithm_id)
    owner_id = _username_of(current_user)
    
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
            "default_params": payload.default_params or {},
            "param_presets": payload.param_presets or {},
        }
    else:
        # 创建新算法
        # 确保算法名称唯一
        _ensure_unique_algorithm_name(r, payload.name)
        created = time.time()
        data = {
            "algorithm_id": algorithm_id,
            "task": payload.task,
            "name": _validate_text_encoding(payload.name, "algorithm.name"),
            "impl": _validate_text_encoding(payload.impl, "algorithm.impl"),
            "version": _validate_text_encoding(payload.version, "algorithm.version"),
            "owner_id": owner_id,
            "created_at": created,
            "default_params": payload.default_params or {},
            "param_presets": payload.param_presets or {},
        }
    
    save_algorithm(r, algorithm_id, data)
    return AlgorithmOut(**data)


@app.patch("/algorithms/{algorithm_id}", response_model=AlgorithmOut)
def patch_algorithm(algorithm_id: str, payload: AlgorithmPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    if algorithm_id in BUILTIN_ALGORITHM_IDS:
        err.api_error(400, err.E_HTTP, "builtin_algorithm_readonly", algorithm_id=algorithm_id)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
        
    if payload.task is not None:
        cur["task"] = payload.task
    if payload.name is not None:
        _ensure_unique_algorithm_name(r, payload.name, exclude_id=algorithm_id)
        cur["name"] = _validate_text_encoding(payload.name, "algorithm.name")
    if payload.impl is not None:
        cur["impl"] = _validate_text_encoding(payload.impl, "algorithm.impl")
    if payload.version is not None:
        cur["version"] = _validate_text_encoding(payload.version, "algorithm.version")
    if payload.default_params is not None:
        cur["default_params"] = payload.default_params
    if payload.param_presets is not None:
        cur["param_presets"] = payload.param_presets
    save_algorithm(r, algorithm_id, cur)
    return AlgorithmOut(**cur)


@app.delete("/algorithms/{algorithm_id}")
def remove_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    if algorithm_id in BUILTIN_ALGORITHM_IDS:
        err.api_error(400, err.E_HTTP, "builtin_algorithm_readonly", algorithm_id=algorithm_id)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
        
    delete_algorithm(r, algorithm_id)
    return {"ok": True, "algorithm_id": algorithm_id}


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
    task_type = (payload.task_type or "").strip().lower()
    dataset_id = (payload.dataset_id or "").strip()
    if task_type not in TASK_LABEL_BY_TYPE:
        err.api_error(400, err.E_BAD_TASK_TYPE, "bad_task_type", task_type=task_type, allowed=list(TASK_LABEL_BY_TYPE.keys()))
    if not dataset_id:
        err.api_error(400, err.E_DATASET_ID_REQUIRED, "dataset_id_required")

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
    if model and int(model.get("feature_dim") or 0) == int(target_context.shape[0]):
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
        runs = list_runs(r, limit=5000, owner_id=(username or None)) or []
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
            run_eff = _normalize_effective_params(run.get("params") if isinstance(run.get("params"), dict) else {})
            if not run_eff:
                continue
            for aid in valid_ids:
                if aid == run_alg_id:
                    continue
                cand_alg = alg_by_id.get(aid) or {}
                cand_base = _scheme_base_name(str(cand_alg.get("name") or ""))
                cand_eff = candidate_defaults.get(aid) or {}
                if not cand_eff:
                    continue
                if cand_base and run_base and cand_base != run_base:
                    continue
                if run_eff != cand_eff:
                    continue
                shadow = dict(run)
                shadow["algorithm_id"] = aid
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

    from .vision.dataset_io import count_paired_images, count_paired_videos

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
    if task_type.startswith("video_"):
        pair_count = count_paired_videos(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt")
    else:
        pair_count = count_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname=input_dirname, gt_dirname="gt")
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

