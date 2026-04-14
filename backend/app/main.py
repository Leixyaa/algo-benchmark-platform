# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import uuid
import io
import csv
import json
import re
import base64
import hashlib
import zipfile
import shutil
import os
import tempfile

from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib import request as urllib_request, error as urllib_error

from openpyxl import Workbook

def _load_local_env_file() -> None:
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env.local"
    if not env_file.is_file():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
    except Exception:
        # 本地环境文件读取失败时不阻断启动，沿用系统环境变量。
        return


_load_local_env_file()

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
    MetricCreate,
    MetricPatch,
    MetricReview,
    MetricPublish,
    MetricOut,
    AlgorithmSubmissionCreate,
    AlgorithmSubmissionReview,
    AlgorithmSubmissionPublish,
    AlgorithmSubmissionOut,
    UserCreate,
    UserPasswordChange,
    UserProfileUpdate,
    UserOut,
    Token,
)
from .store import (
    make_redis,
    save_run,
    load_run,
    delete_run,
    list_runs,
    list_all_runs,
    save_dataset,
    load_dataset,
    delete_dataset,
    list_datasets,
    list_all_datasets,
    save_algorithm,
    load_algorithm,
    delete_algorithm,
    list_algorithms,
    list_all_algorithms,
    save_preset,
    load_preset,
    delete_preset,
    list_presets,
    save_user,
    load_user,
    list_users,
    save_metric,
    load_metric,
    delete_metric,
    list_metrics,
    save_algorithm_submission,
    load_algorithm_submission,
    delete_algorithm_submission,
    list_algorithm_submissions,
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
from . import errors as err, sql_store
from .metric_runtime import validate_python_metric_code
from .vision.dataset_access import IMG_EXTS, VIDEO_EXTS, count_paired_images, count_paired_videos, resolve_dataset_dir

import cv2


app = FastAPI(title="鍥惧儚澶嶅師澧炲己绠楁硶璇勬祴骞冲彴 API", version="0.1.0")

# --- 鐢ㄦ埛绯荤粺 (User System) ---

_ADMIN_USERNAME = os.getenv("ABP_ADMIN_USERNAME", "admin").strip() or "admin"
_ADMIN_PASSWORD = os.getenv("ABP_ADMIN_PASSWORD", "Admin@123456")
RUN_EVAL_MODES = {"preview", "full"}
AI_MAX_HISTORY_ITEMS = 12
AI_DOC_TOPK = 3
_AI_DOC_CACHE: list[dict[str, str]] | None = None


def _ai_bool_env(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _ai_float_env(name: str, default: float) -> float:
    value = str(os.getenv(name, "")).strip()
    if not value:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _ai_int_env(name: str, default: int) -> int:
    value = str(os.getenv(name, "")).strip()
    if not value:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _default_ai_system_prompt() -> str:
    return (
        "你是图像与视频增强复原评测平台的 AI 客服。"
        "请用中文回答，内容简洁、可执行。"
        "严格基于本平台真实功能回答：社区中心、数据集、算法库、指标库、发起评测、任务中心、结果对比、个人信息、我的通知、管理后台。"
        "本平台没有“任务优先级设置”“人工工单系统”等模块，不得虚构。"
        "当用户咨询操作步骤时，优先给出页面路径与按钮名称。"
        "不要输出 markdown 语法符号（如 **、`、#）。"
    )


def _iter_ai_doc_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    patterns = [
        "docs/**/*.md",
        "docs/**/*.txt",
        "release/desktop-runtime/docs/**/*.md",
        "README.md",
        "web/README.md",
    ]
    files: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        for item in root.glob(pattern):
            if not item.is_file():
                continue
            key = str(item.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            files.append(item.resolve())
    return files


def _split_doc_chunks(text: str) -> list[str]:
    raw = str(text or "")
    # 先按空行切段，再截断到较短片段，减少提示词开销。
    chunks = [x.strip() for x in re.split(r"\n\s*\n+", raw) if x.strip()]
    out: list[str] = []
    for item in chunks:
        one = re.sub(r"\s+", " ", item).strip()
        if len(one) < 20:
            continue
        if len(one) > 520:
            one = one[:520].rstrip() + "..."
        out.append(one)
    return out


def _load_ai_doc_corpus() -> list[dict[str, str]]:
    global _AI_DOC_CACHE
    if _AI_DOC_CACHE is not None:
        return _AI_DOC_CACHE
    corpus: list[dict[str, str]] = []
    for path in _iter_ai_doc_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = str(path)
        for chunk in _split_doc_chunks(text):
            corpus.append({"source": rel, "text": chunk})
    _AI_DOC_CACHE = corpus
    return corpus


def _tokenize_for_search(text: str) -> list[str]:
    src = str(text or "").lower()
    # 中文（2+）/英文数字（2+）混合 token
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}", src, flags=re.I)
    dedup: list[str] = []
    seen: set[str] = set()
    for tk in tokens:
        if tk in seen:
            continue
        seen.add(tk)
        dedup.append(tk)
    return dedup


def _retrieve_ai_doc_context(query: str, topk: int = AI_DOC_TOPK) -> tuple[str, list[str]]:
    q = str(query or "").strip()
    if not q:
        return "", []
    q_tokens = _tokenize_for_search(q)
    if not q_tokens:
        return "", []
    corpus = _load_ai_doc_corpus()
    scored: list[tuple[int, dict[str, str]]] = []
    for item in corpus:
        text = item.get("text") or ""
        lower = text.lower()
        score = 0
        for tk in q_tokens:
            if tk in lower:
                score += 2 if len(tk) >= 4 else 1
        if q in text:
            score += 4
        if score <= 0:
            continue
        scored.append((score, item))
    if not scored:
        return "", []
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = scored[: max(1, int(topk))]
    lines: list[str] = []
    for _, item in picked:
        source = item.get("source") or "docs"
        snippet = item.get("text") or ""
        lines.append(f"[{source}] {snippet}")
    sources: list[str] = []
    for _, item in picked:
        src = str(item.get("source") or "").strip()
        if src and src not in sources:
            sources.append(src)
    return "\n".join(lines), sources[: max(1, int(topk))]


def _ai_local_faq_answer(message: str) -> str:
    q = str(message or "").strip().lower()
    if not q:
        return ""
    if ("排队" in q and "运行" in q) or ("一直排队" in q):
        return (
            "任务长时间排队通常与 worker 并发数或当前任务量有关。"
            "你可以在“任务中心”查看状态；若持续不动，先确认后端 worker 是否在线，再适当增加 worker 并发。"
            "本平台不提供任务优先级手动调整。"
        )
    if "怎么发起评测" in q or ("发起" in q and "评测" in q):
        return (
            "进入“发起评测”页面，按步骤选择任务类型、数据集和算法，确认指标后点击“启动评测任务”。"
            "创建后可在“任务中心”查看排队、运行和完成状态。"
        )
    if "算法接入" in q or ("上传" in q and "算法" in q):
        return (
            "进入“算法库”点击“算法接入”，填写任务类型、算法信息并上传代码包，提交后等待审核。"
            "审核通过且接入运行链路后，才能在“发起评测”中用于真实评测。"
        )
    if "数据集上传社区" in q or ("数据集" in q and "审核" in q):
        return (
            "当前版本数据集发布到社区采用发布后治理策略，不走管理员预审核。"
            "若发布后出现问题，可通过管理后台下架、删除或处理举报。"
        )
    if "运行中" in q and "看不到" in q:
        return (
            "任务状态是后端实时更新的，快速任务可能在前端轮询间隔内从排队直接到完成。"
            "你可以在任务详情查看 started_at、finished_at 和耗时字段确认任务确实执行过。"
        )
    if "ai客服" in q and ("接入" in q or "模型" in q):
        return (
            "AI 客服通过后端接口 /ai/chat 调用 OpenAI 兼容模型。"
            "当前支持配置 DeepSeek、豆包等兼容服务，并结合平台文档检索增强回答。"
        )
    if ("综合评分" in q and ("为什么" in q or "怎么" in q)) or "评分怎么算" in q:
        return (
            "综合评分只在真实数据评测场景下计算。"
            "当前按 PSNR、SSIM、NIQE 进行归一化加权，若关键指标缺失会显示为“-”。"
        )
    if ("评分" in q and "-" in q) or ("综合评分" in q and "没有" in q):
        return (
            "综合评分显示“-”通常有三种情况：不是真实数据评测、同组可比样本不足、关键指标缺失。"
            "可在任务详情查看 data_mode 与指标字段确认原因。"
        )
    if ("视频" in q and "评测" in q) or ("视频" in q and "口径" in q):
        return (
            "视频任务使用整段视频逐帧评测并聚合指标，不是只取首帧。"
            "任务详情可查看视频评测模式与样本统计字段。"
        )
    if ("删除" in q and "算法" in q) or ("算法" in q and "已移除" in q):
        return (
            "删除算法后，相关运行任务会执行级联清理；若存在历史记录残留，前端会显示“关联算法已删除”兜底提示。"
            "这样可以保证历史任务可读，不影响验收演示。"
        )
    if ("来源" in q and "文档" in q) or ("回答依据" in q):
        return (
            "AI 客服会优先检索平台文档片段再组织回答。"
            "管理员可开启“显示参考文档来源”查看当前回复引用了哪些文档。"
        )
    if ("为什么" in q and ("优先级" in q or "工单" in q)) or ("没有这个功能" in q):
        return (
            "若你提到“任务优先级、工单系统”等，本平台当前版本确实未提供这些模块。"
            "AI 客服已按平台真实功能约束回答，不会将外部系统能力映射到本平台。"
        )
    if ("验收" in q and ("演示" in q or "怎么讲" in q)) or ("答辩" in q and "讲解" in q):
        return (
            "建议按“数据集 -> 算法库 -> 发起评测 -> 任务中心 -> 结果对比”顺序演示。"
            "每一步强调页面路径、按钮名称和结果闭环，避免泛化描述。"
        )
    return ""


def _ai_local_offline_reply(message: str) -> str:
    q = str(message or "").strip().lower()
    if not q:
        return "你可以问我评测流程、算法接入、任务状态、通知与个人信息等问题。"
    if any(x in q for x in ["你好", "您好", "在吗", "hello", "hi"]):
        return (
            "你好，我在。当前 AI 外部模型未连接，我先用平台内置知识为你解答。"
            "你可以直接问：怎么发起评测、算法接入步骤、排队问题排查。"
        )
    if any(x in q for x in ["谢谢", "感谢", "ok", "好的"]):
        return "不客气。你可以继续问我平台操作问题，我会给你步骤化答案。"
    return (
        "当前 AI 外部模型暂未连接，我先提供平台内置帮助。"
        "可直接提问：发起评测步骤、算法接入步骤、任务排队排查、个人信息与通知操作。"
    )


def _sanitize_ai_reply_text(text: str) -> str:
    out = str(text or "").strip()
    if not out:
        return ""
    out = out.replace("**", "")
    out = out.replace("`", "")
    out = re.sub(r"^\s{0,3}#{1,6}\s*", "", out, flags=re.M)
    out = re.sub(r"^\s*-\s+\*\*(.*?)\*\*\s*", r"- \1 ", out, flags=re.M)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _coerce_chat_messages(history: Any, current_message: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(history, list):
        for item in history[-AI_MAX_HISTORY_ITEMS:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant", "system"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            out.append({"role": role, "content": content})
    current = str(current_message or "").strip()
    if current:
        out.append({"role": "user", "content": current})
    return out


def _ai_extract_text_from_choice(choice_message: Any) -> str:
    if not isinstance(choice_message, dict):
        return ""
    content = choice_message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _call_ai_chat_completion(
    *,
    message: str,
    history: Any,
    context: Any,
    current_user: Optional[dict],
    include_sources: bool = False,
) -> dict[str, Any]:
    faq = _ai_local_faq_answer(message)
    if faq:
        faq_sources: list[str] = []
        if include_sources:
            _, faq_sources = _retrieve_ai_doc_context(message, topk=AI_DOC_TOPK)
        return {
            "reply": faq,
            "provider": "local_faq",
            "model": "rule-based",
            "usage": {},
            "sources": faq_sources,
        }

    enabled = _ai_bool_env("ABP_AI_ENABLED", default=True)
    if not enabled:
        err.api_error(503, err.E_HTTP, "ai_service_disabled")

    api_key = str(os.getenv("ABP_AI_API_KEY", "")).strip()
    base_url = str(os.getenv("ABP_AI_BASE_URL", "https://api.deepseek.com/v1")).strip().rstrip("/")
    model = str(os.getenv("ABP_AI_MODEL", "deepseek-chat")).strip()
    timeout_s = max(3.0, _ai_float_env("ABP_AI_TIMEOUT_S", 20.0))
    temperature = max(0.0, min(1.5, _ai_float_env("ABP_AI_TEMPERATURE", 0.3)))
    max_tokens = max(128, min(4096, _ai_int_env("ABP_AI_MAX_OUTPUT_TOKENS", 800)))
    provider_name = str(os.getenv("ABP_AI_PROVIDER_NAME", "")).strip() or "openai_compatible"
    system_prompt = str(os.getenv("ABP_AI_SYSTEM_PROMPT", "")).strip() or _default_ai_system_prompt()

    if (not api_key) or (not base_url) or (not model):
        return {
            "reply": _ai_local_offline_reply(message),
            "provider": "local_offline",
            "model": "rule-based",
            "usage": {},
            "sources": [],
        }

    route_path = ""
    page_title = ""
    if isinstance(context, dict):
        route_path = str(context.get("route_path") or "").strip()
        page_title = str(context.get("page_title") or "").strip()
    username = _username_of(current_user) or "guest"
    role = _normalize_user_role(current_user)
    doc_context, doc_sources = _retrieve_ai_doc_context(message, topk=AI_DOC_TOPK)
    runtime_context = (
        f"当前登录用户：{username}（{role}）\n"
        f"当前页面路径：{route_path or '-'}\n"
        f"当前页面标题：{page_title or '-'}\n"
        + ("平台文档检索片段：\n" + doc_context + "\n" if doc_context else "")
        + "请优先基于平台文档检索片段回答。若检索片段未覆盖该问题，再给出谨慎建议并明确不确定。"
    )
    messages = [{"role": "system", "content": f"{system_prompt}\n\n{runtime_context}"}]
    messages.extend(_coerce_chat_messages(history, message))
    if len(messages) <= 1:
        err.api_error(400, err.E_HTTP, "empty_user_message")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    endpoint = f"{base_url}/chat/completions"
    req = urllib_request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(e)
        err.api_error(502, err.E_HTTP, "ai_upstream_http_error", status=e.code, detail=detail[:1200])
    except urllib_error.URLError as e:
        err.api_error(502, err.E_HTTP, "ai_upstream_network_error", detail=str(e)[:800])
    except Exception as e:
        err.api_error(502, err.E_HTTP, "ai_upstream_error", detail=str(e)[:800])

    try:
        data = json.loads(raw)
    except Exception:
        err.api_error(502, err.E_HTTP, "ai_upstream_invalid_json")

    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        err.api_error(502, err.E_HTTP, "ai_upstream_empty_choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message_text = _ai_extract_text_from_choice(first.get("message"))
    if not message_text:
        err.api_error(502, err.E_HTTP, "ai_upstream_empty_message")

    usage = data.get("usage") if isinstance(data, dict) else None
    return {
        "reply": _sanitize_ai_reply_text(message_text),
        "provider": provider_name,
        "model": model,
        "usage": usage if isinstance(usage, dict) else {},
        "sources": doc_sources if include_sources else [],
    }


def _normalize_user_role(user: Optional[dict]) -> str:
    role = str((user or {}).get("role") or "user").strip().lower()
    return "admin" if role == "admin" else "user"


def _normalize_eval_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in RUN_EVAL_MODES else "preview"


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
        if not str(current.get("display_name") or "").strip():
            current["display_name"] = "管理员"
            changed = True
        if changed:
            save_user(r, _ADMIN_USERNAME, current)
        return current

    admin_user = {
        "username": _ADMIN_USERNAME,
        "display_name": "管理员",
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
        "display_name": username,
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
        "display_name": str(user.get("display_name") or user.get("username") or ""),
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
        "display_name": str(user.get("display_name") or user.get("username") or ""),
        "role": "admin",
    }


@app.post("/ai/chat")
def ai_chat(
    payload: dict = Body(default={}),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    message = str((payload or {}).get("message") or "").strip()
    if not message:
        err.api_error(400, err.E_HTTP, "message_required")
    history = (payload or {}).get("history")
    context = (payload or {}).get("context")
    raw_include_sources = (payload or {}).get("include_sources")
    if isinstance(raw_include_sources, bool):
        requested_sources = raw_include_sources
    else:
        requested_sources = str(raw_include_sources or "").strip().lower() in {"1", "true", "yes", "on"}
    allow_sources = _normalize_user_role(current_user) == "admin" and requested_sources
    result = _call_ai_chat_completion(
        message=message,
        history=history,
        context=context,
        current_user=current_user,
        include_sources=allow_sources,
    )
    return {
        "ok": True,
        "reply": result.get("reply", ""),
        "provider": result.get("provider", "openai_compatible"),
        "model": result.get("model", ""),
        "usage": result.get("usage", {}),
        "sources": result.get("sources", []),
    }


@app.get("/me", response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserOut(**{
        **current_user,
        "display_name": str((current_user or {}).get("display_name") or (current_user or {}).get("username") or ""),
        "role": _normalize_user_role(current_user),
    })


@app.patch("/me/profile", response_model=UserOut)
def update_me_profile(payload: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    username = _username_of(current_user)
    r = make_redis()
    user = load_user(r, username)
    if not user:
        err.api_error(404, err.E_HTTP, "user_not_found")
    display_name = str(payload.display_name or "").strip()
    if not display_name:
        err.api_error(400, err.E_HTTP, "display_name_required")
    if len(display_name) > 32:
        err.api_error(400, err.E_HTTP, "display_name_too_long")
    user["display_name"] = display_name
    save_user(r, username, user)
    return UserOut(**{
        **user,
        "display_name": display_name,
        "role": _normalize_user_role(user),
    })


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


@app.post("/me/notices/read-all")
def mark_all_notices_read(current_user: dict = Depends(get_current_user)):
    r = make_redis()
    username = _username_of(current_user)
    items = _list_notices(r, username, unread_only=True)
    count = 0
    for item in items:
        if bool(item.get("read")):
            continue
        item["read"] = True
        _save_notice(r, username, item)
        count += 1
    return {"ok": True, "updated": count}


@app.post("/me/notices/clear-read")
def clear_read_notices(current_user: dict = Depends(get_current_user)):
    r = make_redis()
    username = _username_of(current_user)
    items = _list_notices(r, username, unread_only=False)
    deleted = 0
    for item in items:
        if not bool(item.get("read")):
            continue
        notice_id = str(item.get("notice_id") or "").strip()
        if not notice_id:
            continue
        _delete_notice(r, username, notice_id)
        deleted += 1
    return {"ok": True, "deleted": deleted}


@app.post("/me/password")
def change_my_password(payload: UserPasswordChange, current_user: dict = Depends(get_current_user)):
    username = _username_of(current_user)
    r = make_redis()
    user = load_user(r, username)
    if not user:
        err.api_error(404, err.E_HTTP, "user_not_found")
    old_password = str(payload.old_password or "")
    new_password = str(payload.new_password or "")
    if not verify_password(old_password, str(user.get("hashed_password") or "")):
        err.api_error(400, err.E_HTTP, "old_password_incorrect")
    if len(new_password) < 6:
        err.api_error(400, err.E_HTTP, "new_password_too_short")
    if old_password == new_password:
        err.api_error(400, err.E_HTTP, "new_password_same_as_old")
    user["hashed_password"] = get_password_hash(new_password)
    save_user(r, username, user)
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
    allow_origins=["*"],  # 寮€鍙戠幆澧冧笅鍏佽鎵€鏈夋簮
    allow_credentials=False, # 璁句负 False 浠ユ敮鎸?"*"
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
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
VALID_DATASET_TASK_TYPE_KEYS = frozenset(TASK_LABEL_BY_TYPE.keys())


def _normalize_dataset_task_types(raw: Any) -> list[str]:
    """数据集「适用任务」：与平台算法任务键一致，去重保序。"""
    out: list[str] = []
    if raw is None:
        return out
    seq = [raw] if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
    for x in seq:
        k = str(x or "").strip().lower()
        if k in VALID_DATASET_TASK_TYPE_KEYS and k not in out:
            out.append(k)
    return out


def _apply_task_types_from_scan_meta(cur: dict, meta: dict | None) -> None:
    """根据扫描协议得到的 supported_task_types 自动同步到 dataset.task_types。"""
    if not isinstance(meta, dict):
        return
    sup = meta.get("supported_task_types")
    if not isinstance(sup, list):
        return
    cur["task_types"] = _normalize_dataset_task_types(sup)


def _require_task_types_for_user_public_dataset(cur: dict) -> None:
    """用户数据集公开到社区前须有可识别的适用任务（task_types 或扫描 meta）。"""
    if str(cur.get("owner_id") or "").strip() == "system":
        return
    if str(cur.get("visibility") or "private").strip().lower() != "public":
        return
    tts = _normalize_dataset_task_types(cur.get("task_types"))
    if len(tts) >= 1:
        return
    meta = cur.get("meta") if isinstance(cur.get("meta"), dict) else {}
    sup = meta.get("supported_task_types") if isinstance(meta.get("supported_task_types"), list) else []
    if len(_normalize_dataset_task_types(sup)) >= 1:
        return
    err.api_error(
        400,
        err.E_HTTP,
        "dataset_task_types_required_for_public",
        allowed=sorted(VALID_DATASET_TASK_TYPE_KEYS),
    )
VALID_METRIC_DIRECTIONS = {"higher_better", "lower_better"}
VALID_METRIC_IMPLEMENTATION_TYPES = {"builtin", "python", "formula"}
VALID_METRIC_STATUSES = {"pending", "approved", "rejected"}
VALID_ALGORITHM_SUBMISSION_STATUSES = {"pending", "approved", "rejected"}

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


def _algorithm_submission_storage_root() -> Path:
    root = _dataset_storage_root() / "_algorithm_submissions"
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
        raw_path = Path(storage_path)
        if raw_path.is_absolute():
            return raw_path
        repo_root = Path(__file__).resolve().parents[2]
        backend_root = Path(__file__).resolve().parents[1]
        candidates = [
            repo_root / raw_path,
            backend_root / raw_path,
            _dataset_storage_root() / raw_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return (repo_root / raw_path).resolve(strict=False)
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
    base = str(base_name or "涓嬭浇绠楁硶").strip() or "涓嬭浇绠楁硶"
    if not _algorithm_name_exists(r, base):
        return base
    idx = 2
    while _algorithm_name_exists(r, f"{base} #{idx}"):
        idx += 1
    return f"{base} #{idx}"


def _algorithm_name_exists_for_owner(
    r,
    owner_id: str,
    name: str,
    exclude_id: str | None = None,
    ignore_submission_id: str | None = None,
) -> bool:
    owner = str(owner_id or "").strip()
    wanted = _normalize_algorithm_name(name)
    ignored_submission_id = str(ignore_submission_id or "").strip()
    if not owner or not wanted:
        return False
    for x in list_algorithms(r, limit=5000, owner_id=owner, include_public=True) or []:
        aid = str(x.get("algorithm_id") or "")
        if exclude_id and aid == exclude_id:
            continue
        if str(x.get("owner_id") or "").strip() != owner:
            continue
        if ignored_submission_id and str(x.get("source_submission_id") or "").strip() == ignored_submission_id:
            continue
        if _normalize_algorithm_name(x.get("name") or "") == wanted:
            return True
    return False


def _make_owner_unique_algorithm_name(
    r,
    owner_id: str,
    base_name: str,
    exclude_id: str | None = None,
    ignore_submission_id: str | None = None,
) -> str:
    base = str(base_name or "涓嬭浇绠楁硶").strip() or "涓嬭浇绠楁硶"
    if not _algorithm_name_exists_for_owner(
        r,
        owner_id,
        base,
        exclude_id=exclude_id,
        ignore_submission_id=ignore_submission_id,
    ):
        return base
    idx = 2
    while _algorithm_name_exists_for_owner(
        r,
        owner_id,
        f"{base} #{idx}",
        exclude_id=exclude_id,
        ignore_submission_id=ignore_submission_id,
    ):
        idx += 1
    return f"{base} #{idx}"


def _algorithm_submission_display_name(submission: dict, fallback: str = "") -> str:
    return str(submission.get("name") or fallback or "用户接入算法").strip() or "用户接入算法"


def _repair_submission_community_algorithm_names(r, owner_id: str | None = None) -> None:
    owner_filter = str(owner_id or "").strip()
    for submission in list_algorithm_submissions(r, limit=5000) or []:
        submission_owner = str(submission.get("owner_id") or "").strip()
        if owner_filter and submission_owner != owner_filter:
            continue
        community_algorithm_id = str(submission.get("community_algorithm_id") or "").strip()
        expected_name = str(submission.get("name") or "").strip()
        if not community_algorithm_id or not expected_name:
            continue
        algorithm = load_algorithm(r, community_algorithm_id)
        if not algorithm or str(algorithm.get("owner_id") or "").strip() != submission_owner:
            continue
        current_name = str(algorithm.get("name") or "").strip()
        if current_name == expected_name:
            continue
        if not re.fullmatch(rf"{re.escape(expected_name)}\s+#\d+", current_name):
            continue
        repaired_name = _algorithm_submission_display_name(submission, expected_name)
        if repaired_name != current_name:
            algorithm["name"] = repaired_name
            save_algorithm(r, community_algorithm_id, algorithm)


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


def _algorithm_submission_dir(owner_id: str, submission_id: str) -> Path:
    return _algorithm_submission_storage_root() / str(owner_id or "system") / submission_id


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
    # 鍙鐞嗘病鏈夋墍鏈夎€呯殑鏁版嵁闆嗗拰绠楁硶
    for data in list_all_datasets(r, limit=5000):
        if not isinstance(data, dict) or "dataset_id" not in data:
            continue
        # 缺少 owner_id 的历史数据补为 system
        if not data.get("owner_id"):
            data["owner_id"] = "system"
            save_dataset(r, str(data.get("dataset_id") or ""), data)

    for data in list_all_algorithms(r, limit=5000):
        if not isinstance(data, dict) or "algorithm_id" not in data:
            continue
        alg_id = str(data.get("algorithm_id") or "")
        # 鍙湁褰撴病鏈夋墍鏈夎€呮椂锛屾墠璁剧疆涓虹郴缁熸墍鏈夎€呮垨_PINNED_OWNER_USERNAME
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

    add("alg_dn_cnn", "鍘诲櫔", "FastNLMeans(鍩虹嚎)",
        {"nlm_h": 10, "nlm_hColor": 10, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
        {"speed": {"nlm_h": 7, "nlm_hColor": 7, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 15},
         "quality": {"nlm_h": 12, "nlm_hColor": 12, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21}})
    add("alg_dn_cnn_light", "鍘诲櫔", "FastNLMeans-杞诲害(鍩虹嚎)",
        {"nlm_h": 7, "nlm_hColor": 7, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 15},
        {"speed": {"nlm_h": 5, "nlm_hColor": 5, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 11},
         "quality": {"nlm_h": 9, "nlm_hColor": 9, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 17}})
    add("alg_dn_cnn_strong", "鍘诲櫔", "FastNLMeans-澧炲己(鍩虹嚎)",
        {"nlm_h": 14, "nlm_hColor": 14, "nlm_templateWindowSize": 9, "nlm_searchWindowSize": 25},
        {"speed": {"nlm_h": 12, "nlm_hColor": 12, "nlm_templateWindowSize": 7, "nlm_searchWindowSize": 21},
         "quality": {"nlm_h": 16, "nlm_hColor": 16, "nlm_templateWindowSize": 11, "nlm_searchWindowSize": 31}})
    add("alg_denoise_bilateral", "鍘诲櫔", "Bilateral(鍩虹嚎)", {"bilateral_d": 7, "bilateral_sigmaColor": 35, "bilateral_sigmaSpace": 35},
        {"speed": {"bilateral_d": 5, "bilateral_sigmaColor": 25, "bilateral_sigmaSpace": 25},
         "quality": {"bilateral_d": 9, "bilateral_sigmaColor": 50, "bilateral_sigmaSpace": 50}})
    add("alg_denoise_bilateral_soft", "鍘诲櫔", "Bilateral-杞诲害(鍩虹嚎)", {"bilateral_d": 5, "bilateral_sigmaColor": 20, "bilateral_sigmaSpace": 20},
        {"speed": {"bilateral_d": 3, "bilateral_sigmaColor": 15, "bilateral_sigmaSpace": 15},
         "quality": {"bilateral_d": 7, "bilateral_sigmaColor": 28, "bilateral_sigmaSpace": 28}})
    add("alg_denoise_bilateral_strong", "鍘诲櫔", "Bilateral-澧炲己(鍩虹嚎)", {"bilateral_d": 11, "bilateral_sigmaColor": 60, "bilateral_sigmaSpace": 60},
        {"speed": {"bilateral_d": 9, "bilateral_sigmaColor": 50, "bilateral_sigmaSpace": 50},
         "quality": {"bilateral_d": 13, "bilateral_sigmaColor": 75, "bilateral_sigmaSpace": 75}})
    add("alg_denoise_gaussian", "鍘诲櫔", "Gaussian(鍩虹嚎)", {"gaussian_sigma": 1.0}, {"speed": {"gaussian_sigma": 0.8}, "quality": {"gaussian_sigma": 1.2}})
    add("alg_denoise_gaussian_light", "鍘诲櫔", "Gaussian-杞诲害(鍩虹嚎)", {"gaussian_sigma": 0.6}, {"speed": {"gaussian_sigma": 0.4}, "quality": {"gaussian_sigma": 0.8}})
    add("alg_denoise_gaussian_strong", "鍘诲櫔", "Gaussian-澧炲己(鍩虹嚎)", {"gaussian_sigma": 1.6}, {"speed": {"gaussian_sigma": 1.2}, "quality": {"gaussian_sigma": 2.0}})
    add("alg_denoise_median", "鍘诲櫔", "Median(鍩虹嚎)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_denoise_median_light", "鍘诲櫔", "Median-杞诲害(鍩虹嚎)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_denoise_median_strong", "鍘诲櫔", "Median-澧炲己(鍩虹嚎)", {"median_ksize": 7}, {"speed": {"median_ksize": 5}, "quality": {"median_ksize": 9}})

    add("alg_dehaze_dcp", "鍘婚浘", "DCP鏆楅€氶亾鍏堥獙(鍩虹嚎)", {"dcp_patch": 15, "dcp_omega": 0.95, "dcp_t0": 0.1},
        {"speed": {"dcp_patch": 7, "dcp_omega": 0.9, "dcp_t0": 0.12}, "quality": {"dcp_patch": 21, "dcp_omega": 0.97, "dcp_t0": 0.08}})
    add("alg_dehaze_dcp_fast", "鍘婚浘", "DCP-蹇€?鍩虹嚎)", {"dcp_patch": 7, "dcp_omega": 0.9, "dcp_t0": 0.12},
        {"speed": {"dcp_patch": 5, "dcp_omega": 0.88, "dcp_t0": 0.14}, "quality": {"dcp_patch": 11, "dcp_omega": 0.93, "dcp_t0": 0.1}})
    add("alg_dehaze_dcp_strong", "鍘婚浘", "DCP-澧炲己(鍩虹嚎)", {"dcp_patch": 23, "dcp_omega": 0.98, "dcp_t0": 0.08},
        {"speed": {"dcp_patch": 19, "dcp_omega": 0.96, "dcp_t0": 0.09}, "quality": {"dcp_patch": 27, "dcp_omega": 0.99, "dcp_t0": 0.06}})
    add("alg_dehaze_clahe", "鍘婚浘", "CLAHE(鍩虹嚎)", {"clahe_clip_limit": 2.0}, {"speed": {"clahe_clip_limit": 1.5}, "quality": {"clahe_clip_limit": 3.0}})
    add("alg_dehaze_clahe_mild", "鍘婚浘", "CLAHE-杞诲害(鍩虹嚎)", {"clahe_clip_limit": 1.5}, {"speed": {"clahe_clip_limit": 1.2}, "quality": {"clahe_clip_limit": 2.0}})
    add("alg_dehaze_clahe_strong", "鍘婚浘", "CLAHE-澧炲己(鍩虹嚎)", {"clahe_clip_limit": 3.5}, {"speed": {"clahe_clip_limit": 3.0}, "quality": {"clahe_clip_limit": 4.5}})
    add("alg_dehaze_gamma", "鍘婚浘", "Gamma(鍩虹嚎)", {"gamma": 0.75}, {"speed": {"gamma": 0.8}, "quality": {"gamma": 0.65}})
    add("alg_dehaze_gamma_mild", "鍘婚浘", "Gamma-杞诲害(鍩虹嚎)", {"gamma": 0.85}, {"speed": {"gamma": 0.9}, "quality": {"gamma": 0.78}})
    add("alg_dehaze_gamma_strong", "鍘婚浘", "Gamma-澧炲己(鍩虹嚎)", {"gamma": 0.6}, {"speed": {"gamma": 0.65}, "quality": {"gamma": 0.5}})

    add("alg_deblur_unsharp", "去模糊", "UnsharpMask(鍩虹嚎)", {"unsharp_sigma": 1.0, "unsharp_amount": 1.6},
        {"speed": {"unsharp_sigma": 0.8, "unsharp_amount": 1.2}, "quality": {"unsharp_sigma": 1.2, "unsharp_amount": 2.0}})
    add("alg_deblur_unsharp_light", "去模糊", "Unsharp-杞诲害(鍩虹嚎)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})
    add("alg_deblur_unsharp_strong", "去模糊", "Unsharp-澧炲己(鍩虹嚎)", {"unsharp_sigma": 1.3, "unsharp_amount": 2.4},
        {"speed": {"unsharp_sigma": 1.1, "unsharp_amount": 2.0}, "quality": {"unsharp_sigma": 1.6, "unsharp_amount": 2.8}})
    add("alg_deblur_laplacian", "去模糊", "LaplacianSharpen(鍩虹嚎)", {"laplacian_strength": 0.7}, {"speed": {"laplacian_strength": 0.5}, "quality": {"laplacian_strength": 0.9}})
    add("alg_deblur_laplacian_light", "去模糊", "Laplacian-杞诲害(鍩虹嚎)", {"laplacian_strength": 0.5}, {"speed": {"laplacian_strength": 0.35}, "quality": {"laplacian_strength": 0.7}})
    add("alg_deblur_laplacian_strong", "去模糊", "Laplacian-澧炲己(鍩虹嚎)", {"laplacian_strength": 1.1}, {"speed": {"laplacian_strength": 0.9}, "quality": {"laplacian_strength": 1.4}})

    add("alg_sr_nearest", "瓒呭垎杈ㄧ巼", "Nearest(鍩虹嚎)")
    add("alg_sr_linear", "瓒呭垎杈ㄧ巼", "Linear(鍩虹嚎)")
    add("alg_sr_bicubic", "瓒呭垎杈ㄧ巼", "Bicubic(鍩虹嚎)")
    add("alg_sr_bicubic_sharp", "瓒呭垎杈ㄧ巼", "Bicubic-Sharp(鍩虹嚎)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.3},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.1}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6}})
    add("alg_sr_lanczos", "瓒呭垎杈ㄧ巼", "Lanczos(鍩虹嚎)")
    add("alg_sr_lanczos_sharp", "瓒呭垎杈ㄧ巼", "Lanczos-Sharp(鍩虹嚎)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})

    add("alg_lowlight_gamma", "低照度增强", "Gamma(鍩虹嚎)", {"lowlight_gamma": 0.6}, {"speed": {"lowlight_gamma": 0.7}, "quality": {"lowlight_gamma": 0.55}})
    add("alg_lowlight_gamma_soft", "低照度增强", "Gamma-杞诲害(鍩虹嚎)", {"lowlight_gamma": 0.75}, {"speed": {"lowlight_gamma": 0.8}, "quality": {"lowlight_gamma": 0.65}})
    add("alg_lowlight_gamma_strong", "低照度增强", "Gamma-澧炲己(鍩虹嚎)", {"lowlight_gamma": 0.45}, {"speed": {"lowlight_gamma": 0.5}, "quality": {"lowlight_gamma": 0.35}})
    add("alg_lowlight_clahe", "低照度增强", "CLAHE(鍩虹嚎)", {"clahe_clip_limit": 2.5}, {"speed": {"clahe_clip_limit": 2.0}, "quality": {"clahe_clip_limit": 3.5}})
    add("alg_lowlight_clahe_soft", "低照度增强", "CLAHE-杞诲害(鍩虹嚎)", {"clahe_clip_limit": 1.8}, {"speed": {"clahe_clip_limit": 1.5}, "quality": {"clahe_clip_limit": 2.4}})
    add("alg_lowlight_clahe_strong", "低照度增强", "CLAHE-澧炲己(鍩虹嚎)", {"clahe_clip_limit": 3.8}, {"speed": {"clahe_clip_limit": 3.2}, "quality": {"clahe_clip_limit": 4.5}})
    add("alg_lowlight_hybrid", "低照度增强", "Gamma-CLAHE娣峰悎(鍩虹嚎)", {"lowlight_gamma": 0.62, "clahe_clip_limit": 2.6},
        {"speed": {"lowlight_gamma": 0.7, "clahe_clip_limit": 2.2}, "quality": {"lowlight_gamma": 0.55, "clahe_clip_limit": 3.2}})

    add("alg_video_denoise_gaussian", "瑙嗛鍘诲櫔", "Video-Gaussian(鍩虹嚎)", {"gaussian_sigma": 1.0}, {"speed": {"gaussian_sigma": 0.8}, "quality": {"gaussian_sigma": 1.2}})
    add("alg_video_denoise_gaussian_light", "瑙嗛鍘诲櫔", "Video-Gaussian-杞诲害(鍩虹嚎)", {"gaussian_sigma": 0.6}, {"speed": {"gaussian_sigma": 0.4}, "quality": {"gaussian_sigma": 0.8}})
    add("alg_video_denoise_gaussian_strong", "瑙嗛鍘诲櫔", "Video-Gaussian-澧炲己(鍩虹嚎)", {"gaussian_sigma": 1.6}, {"speed": {"gaussian_sigma": 1.2}, "quality": {"gaussian_sigma": 2.0}})
    add("alg_video_denoise_median", "瑙嗛鍘诲櫔", "Video-Median(鍩虹嚎)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_video_denoise_median_light", "瑙嗛鍘诲櫔", "Video-Median-杞诲害(鍩虹嚎)", {"median_ksize": 3}, {"speed": {"median_ksize": 3}, "quality": {"median_ksize": 5}})
    add("alg_video_denoise_median_strong", "瑙嗛鍘诲櫔", "Video-Median-澧炲己(鍩虹嚎)", {"median_ksize": 7}, {"speed": {"median_ksize": 5}, "quality": {"median_ksize": 9}})

    add("alg_video_sr_nearest", "瑙嗛瓒呭垎", "Video-Nearest(鍩虹嚎)")
    add("alg_video_sr_linear", "瑙嗛瓒呭垎", "Video-Linear(鍩虹嚎)")
    add("alg_video_sr_bicubic", "瑙嗛瓒呭垎", "Video-Bicubic(鍩虹嚎)")
    add("alg_video_sr_bicubic_sharp", "瑙嗛瓒呭垎", "Video-Bicubic-Sharp(鍩虹嚎)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.3},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.1}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.6}})
    add("alg_video_sr_lanczos", "瑙嗛瓒呭垎", "Video-Lanczos(鍩虹嚎)")
    add("alg_video_sr_lanczos_sharp", "瑙嗛瓒呭垎", "Video-Lanczos-Sharp(鍩虹嚎)", {"unsharp_sigma": 0.8, "unsharp_amount": 1.2},
        {"speed": {"unsharp_sigma": 0.6, "unsharp_amount": 1.0}, "quality": {"unsharp_sigma": 1.0, "unsharp_amount": 1.5}})
    return items


def _builtin_metric_catalog():
    task_types = sorted(TASK_LABEL_BY_TYPE.keys())
    created = time.time()
    return [
        {
            "metric_id": "metric_psnr",
            "metric_key": "PSNR",
            "name": "PSNR",
            "display_name": "PSNR",
            "description": "峰值信噪比，用于衡量复原结果与 GT 图像的像素误差。",
            "task_types": task_types,
            "direction": "higher_better",
            "requires_reference": True,
            "implementation_type": "builtin",
            "formula_text": "",
            "code_text": "",
            "owner_id": "system",
            "status": "approved",
            "runtime_ready": True,
            "review_note": "平台内置指标，已接入运行链路。",
            "reviewed_by": "system",
            "reviewed_at": created,
            "created_at": created,
        },
        {
            "metric_id": "metric_ssim",
            "metric_key": "SSIM",
            "name": "SSIM",
            "display_name": "SSIM",
            "description": "结构相似性指标，用于衡量复原结果与 GT 在结构层面的相似程度。",
            "task_types": task_types,
            "direction": "higher_better",
            "requires_reference": True,
            "implementation_type": "builtin",
            "formula_text": "",
            "code_text": "",
            "owner_id": "system",
            "status": "approved",
            "runtime_ready": True,
            "review_note": "平台内置指标，已接入运行链路。",
            "reviewed_by": "system",
            "reviewed_at": created,
            "created_at": created,
        },
        {
            "metric_id": "metric_niqe",
            "metric_key": "NIQE",
            "name": "NIQE",
            "display_name": "NIQE",
            "description": "自然图像质量评价指标，无需 GT，数值越低通常代表质量越好。",
            "task_types": task_types,
            "direction": "lower_better",
            "requires_reference": False,
            "implementation_type": "builtin",
            "formula_text": "",
            "code_text": "",
            "owner_id": "system",
            "status": "approved",
            "runtime_ready": True,
            "review_note": "平台内置指标，已接入运行链路。",
            "reviewed_by": "system",
            "reviewed_at": created,
            "created_at": created,
        },
    ]


def _normalize_metric_key(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip()).strip("_").upper()


def _make_metric_key(name: str, fallback_prefix: str = "USER_METRIC") -> str:
    key = _normalize_metric_key(name)
    if key:
        return key
    return f"{fallback_prefix}_{uuid.uuid4().hex[:8].upper()}"


def _metric_key_exists(r, metric_key: str, exclude_id: str | None = None) -> bool:
    wanted = _normalize_metric_key(metric_key)
    if not wanted:
        return False
    for item in list_metrics(r, limit=5000) or []:
        metric_id = str(item.get("metric_id") or "")
        if exclude_id and metric_id == exclude_id:
            continue
        if _normalize_metric_key(item.get("metric_key") or "") == wanted:
            return True
    return False


def _assert_unique_metric_key(r, metric_key: str, exclude_id: str | None = None) -> str:
    normalized = _normalize_metric_key(metric_key)
    if not normalized:
        err.api_error(400, err.E_HTTP, "metric_key_required")
    if _metric_key_exists(r, normalized, exclude_id=exclude_id):
        err.api_error(409, err.E_HTTP, "metric_key_exists", metric_key=normalized)
    return normalized


def _resolve_metric_key_for_create(r, metric_key: str | None, name: str | None) -> str:
    requested = str(metric_key or "").strip()
    if requested:
        normalized = _normalize_metric_key(requested)
        if normalized:
            return _assert_unique_metric_key(r, normalized)
    fallback = _make_metric_key(name or requested or "USER_METRIC")
    return _assert_unique_metric_key(r, fallback)


def _resolve_metric_key_for_patch(r, metric_id: str, metric_key: str | None, name: str | None) -> str:
    requested = str(metric_key or "").strip()
    if requested:
        normalized = _normalize_metric_key(requested)
        if normalized:
            return _assert_unique_metric_key(r, normalized, exclude_id=metric_id)
    fallback = _make_metric_key(name or requested or "USER_METRIC")
    return _assert_unique_metric_key(r, fallback, exclude_id=metric_id)


def _make_unique_metric_copy_key(r, source_key: str, target_owner: str) -> str:
    base = _normalize_metric_key(f"{source_key or 'COMMUNITY_METRIC'}_{target_owner or 'USER'}")
    if not base:
        base = f"COMMUNITY_METRIC_{uuid.uuid4().hex[:8].upper()}"
    candidate = base
    idx = 2
    while _metric_key_exists(r, candidate):
        candidate = f"{base}_{idx}"
        idx += 1
    return candidate


def _normalize_metric_task_types(task_types: list[str] | None) -> list[str]:
    items = []
    for item in (task_types or []):
        raw = str(item or "").strip()
        task_type = TASK_TYPE_BY_LABEL.get(raw, raw).strip().lower()
        if task_type in TASK_LABEL_BY_TYPE and task_type not in items:
            items.append(task_type)
    return items


def _normalize_metric_direction(direction: str | None) -> str:
    value = str(direction or "").strip().lower()
    if value not in VALID_METRIC_DIRECTIONS:
        err.api_error(400, err.E_HTTP, "metric_direction_invalid", allowed=sorted(VALID_METRIC_DIRECTIONS))
    return value


def _normalize_metric_implementation_type(implementation_type: str | None) -> str:
    value = str(implementation_type or "").strip().lower()
    if value not in VALID_METRIC_IMPLEMENTATION_TYPES:
        err.api_error(400, err.E_HTTP, "metric_implementation_type_invalid", allowed=sorted(VALID_METRIC_IMPLEMENTATION_TYPES))
    return value


def _normalize_metric_status(status: str | None) -> str:
    value = str(status or "").strip().lower()
    if value not in VALID_METRIC_STATUSES:
        err.api_error(400, err.E_HTTP, "metric_status_invalid", allowed=sorted(VALID_METRIC_STATUSES))
    return value


def _normalize_algorithm_submission_status(status: str | None) -> str:
    value = str(status or "").strip().lower()
    if value not in VALID_ALGORITHM_SUBMISSION_STATUSES:
        err.api_error(400, err.E_HTTP, "algorithm_submission_status_invalid", allowed=sorted(VALID_ALGORITHM_SUBMISSION_STATUSES))
    return value


def _list_all_algorithm_submissions(r) -> list[dict]:
    return list_algorithm_submissions(r, limit=5000) or []


def _algorithm_submission_to_out(r, item: dict, cache: dict[str, str] | None = None) -> dict:
    data = _with_owner_display_name(r, item, cache=cache)
    task_type = str(data.get("task_type") or "").strip().lower()
    data["task_label"] = TASK_LABEL_BY_TYPE.get(task_type, "")
    return AlgorithmSubmissionOut(**data).model_dump()


def _infer_user_package_role(algorithm: dict | None) -> str:
    if not isinstance(algorithm, dict):
        return ""
    explicit = str(algorithm.get("package_role") or "").strip().lower()
    if explicit:
        return explicit
    impl = str(algorithm.get("impl") or "").strip().lower()
    if impl != "userpackage":
        return ""
    owner_id = str(algorithm.get("owner_id") or "system").strip() or "system"
    visibility = str(algorithm.get("visibility") or "private").strip().lower()
    source_algorithm_id = str(algorithm.get("source_algorithm_id") or "").strip()
    source_submission_id = str(algorithm.get("source_submission_id") or "").strip()
    if owner_id == "system":
        return "platform"
    if source_algorithm_id:
        return "downloaded_community"
    if visibility == "public" and source_submission_id:
        return "community"
    if source_submission_id:
        return "owner_runtime"
    return ""


def _is_submission_owner_runtime_algorithm(algorithm: dict | None, submission_id: str, owner_id: str) -> bool:
    if not isinstance(algorithm, dict):
        return False
    if str(algorithm.get("owner_id") or "").strip() != str(owner_id or "").strip():
        return False
    if str(algorithm.get("source_submission_id") or "").strip() != str(submission_id or "").strip():
        return False
    role = _infer_user_package_role(algorithm)
    if role == "owner_runtime":
        return True
    visibility = str(algorithm.get("visibility") or "private").strip().lower()
    return visibility != "public" and not bool(algorithm.get("allow_download")) and not str(algorithm.get("source_algorithm_id") or "").strip()


def _is_submission_community_algorithm(algorithm: dict | None, submission_id: str, owner_id: str) -> bool:
    if not isinstance(algorithm, dict):
        return False
    if str(algorithm.get("owner_id") or "").strip() != str(owner_id or "").strip():
        return False
    if str(algorithm.get("source_submission_id") or "").strip() != str(submission_id or "").strip():
        return False
    role = _infer_user_package_role(algorithm)
    if role == "community":
        return True
    return str(algorithm.get("visibility") or "").strip().lower() == "public" and not str(algorithm.get("source_algorithm_id") or "").strip()


def _is_userpackage_download_runtime_ready(algorithm: dict | None) -> bool:
    if not isinstance(algorithm, dict):
        return False
    impl = str(algorithm.get("impl") or "").strip().lower()
    if impl != "userpackage":
        return False
    archive_path = str(algorithm.get("archive_path") or "").strip()
    archive_filename = str(algorithm.get("archive_filename") or "").strip()
    return bool(archive_path or archive_filename)


def _ensure_submission_owner_algorithm_synced(r, submission: dict) -> dict:
    cur = dict(submission or {})
    submission_id = str(cur.get("submission_id") or "").strip()
    owner_id = str(cur.get("owner_id") or "").strip()
    status = str(cur.get("status") or "").strip().lower()
    if not submission_id or not owner_id:
        return cur

    changed = False
    owner_algorithm_id = str(cur.get("owner_algorithm_id") or "").strip()
    owner_algorithm = load_algorithm(r, owner_algorithm_id) if owner_algorithm_id else None
    if not _is_submission_owner_runtime_algorithm(owner_algorithm, submission_id, owner_id):
        owner_algorithm = None
        owner_algorithm_id = ""
        for item in list_algorithms(r, limit=5000, owner_id=owner_id, include_public=True) or []:
            if not _is_submission_owner_runtime_algorithm(item, submission_id, owner_id):
                continue
            owner_algorithm = item
            owner_algorithm_id = str(item.get("algorithm_id") or "").strip()
            break
        if str(cur.get("owner_algorithm_id") or "").strip() != owner_algorithm_id:
            cur["owner_algorithm_id"] = owner_algorithm_id or None
            changed = True

    if status == "approved":
        expected_runtime_ready = bool(cur.get("runtime_ready"))
        new_owner_algorithm_id = _upsert_algorithm_submission_owner_algorithm(r, cur, runtime_ready=expected_runtime_ready)
        if new_owner_algorithm_id != str(cur.get("owner_algorithm_id") or "").strip():
            cur["owner_algorithm_id"] = new_owner_algorithm_id
            changed = True
    elif owner_algorithm_id:
        _set_platform_algorithm_runtime_state(r, owner_algorithm_id, False)

    if changed:
        save_algorithm_submission(r, submission_id, cur)
    return cur


def _decode_algorithm_submission_archive(data_b64: str) -> bytes:
    raw = str(data_b64 or "").strip()
    if not raw:
        err.api_error(400, err.E_HTTP, "algorithm_archive_required")
    try:
        payload = base64.b64decode(raw.encode("utf-8"), validate=True)
    except Exception:
        err.api_error(400, err.E_HTTP, "algorithm_archive_invalid_base64")
    if not payload:
        err.api_error(400, err.E_HTTP, "algorithm_archive_empty")
    if len(payload) > 20 * 1024 * 1024:
        err.api_error(400, err.E_HTTP, "algorithm_archive_too_large", max_bytes=20 * 1024 * 1024)
    return payload


def _store_algorithm_submission_archive(owner_id: str, submission_id: str, archive_filename: str, payload: bytes) -> tuple[str, int, str]:
    safe_name = Path(str(archive_filename or "").strip() or "algorithm_package.zip").name
    target_dir = _algorithm_submission_dir(owner_id, submission_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    with open(target_path, "wb") as f:
        f.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return str(target_path), len(payload), digest


def _algorithm_archive_response(archive_path: Path, filename: str):
    archive_path = archive_path.resolve()
    if not archive_path.exists() or not archive_path.is_file():
        return None
    safe_name = Path(str(filename or "").strip() or archive_path.name).name or archive_path.name
    return StreamingResponse(
        open(archive_path, "rb"),
        media_type="application/octet-stream",
        headers=_attachment_headers(safe_name),
    )


def _attachment_headers(filename: str) -> dict[str, str]:
    safe_name = Path(str(filename or "").strip() or "download.bin").name or "download.bin"
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', "_", safe_name).strip("._") or "download"
    suffix = Path(safe_name).suffix
    if suffix and not ascii_name.endswith(suffix):
        ascii_name = f"{ascii_name}{suffix}"
    return {
        "Content-Disposition": f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(safe_name)}'
    }


def _resolve_algorithm_archive_response(r, algorithm: dict):
    archive_path = str((algorithm or {}).get("archive_path") or "").strip()
    archive_filename = str((algorithm or {}).get("archive_filename") or "").strip()
    if archive_path:
        response = _algorithm_archive_response(Path(archive_path), archive_filename)
        if response is not None:
            return response

    submission_id = str((algorithm or {}).get("source_submission_id") or "").strip()
    if submission_id:
        submission = load_algorithm_submission(r, submission_id)
        if submission:
            response = _algorithm_archive_response(
                Path(str(submission.get("archive_path") or "")),
                str(submission.get("archive_filename") or archive_filename or ""),
            )
            if response is not None:
                return response
    return None


def _set_platform_algorithm_runtime_state(r, algorithm_id: str, runtime_ready: bool) -> None:
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        return
    ready = bool(runtime_ready)
    cur["runtime_ready"] = ready
    cur["is_active"] = ready
    cur["allow_use"] = ready
    save_algorithm(r, algorithm_id, cur)


def _promote_algorithm_submission_to_platform(r, submission: dict, runtime_ready: bool = False) -> str:
    existing_id = str(submission.get("platform_algorithm_id") or "").strip()
    if existing_id and load_algorithm(r, existing_id):
        _set_platform_algorithm_runtime_state(r, existing_id, runtime_ready)
        return existing_id
    submission_id = str(submission.get("submission_id") or "").strip()
    source_owner = str(submission.get("owner_id") or "").strip() or "system"
    task_type = str(submission.get("task_type") or "").strip().lower()
    task_label = TASK_LABEL_BY_TYPE.get(task_type, "")
    base_name = str(submission.get("name") or submission_id or "待接入算法").strip() or "待接入算法"
    platform_id = _make_platform_algorithm_id(r, f"submission_{submission_id}")
    description_parts = [str(submission.get("description") or "").strip()]
    dependency_text = str(submission.get("dependency_text") or "").strip()
    entry_text = str(submission.get("entry_text") or "").strip()
    if dependency_text:
        description_parts.append(f"依赖说明：{dependency_text}")
    if entry_text:
        description_parts.append(f"入口说明：{entry_text}")
    description_parts.append("该算法由用户代码包提交并经管理员审核留档，当前仍处于受控接入阶段，尚未进入自动执行链路。")
    data = {
        "algorithm_id": platform_id,
        "task": task_label,
        "name": _make_unique_algorithm_name(r, base_name),
        "impl": "UserPackage",
        "version": str(submission.get("version") or "v1").strip() or "v1",
        "description": " ".join([x for x in description_parts if x]),
        "owner_id": "system",
        "created_at": time.time(),
        "default_params": {},
        "param_presets": {},
        "visibility": "private",
        "allow_use": bool(runtime_ready),
        "allow_download": False,
        "is_active": bool(runtime_ready),
        "runtime_ready": bool(runtime_ready),
        "source_submission_id": submission_id,
        "source_owner_id": source_owner,
        "package_role": "platform",
        "dependency_text": dependency_text,
        "entry_text": entry_text,
        "archive_filename": str(submission.get("archive_filename") or ""),
        "archive_sha256": str(submission.get("archive_sha256") or ""),
        "archive_path": str(submission.get("archive_path") or ""),
    }
    save_algorithm(r, platform_id, data)
    return platform_id


def _upsert_algorithm_submission_owner_algorithm(r, submission: dict, runtime_ready: bool = False) -> str:
    submission_id = str(submission.get("submission_id") or "").strip()
    if not submission_id:
        err.api_error(400, err.E_HTTP, "submission_id_required")
    owner_id = str(submission.get("owner_id") or "").strip()
    if not owner_id:
        err.api_error(400, err.E_HTTP, "submission_owner_required", submission_id=submission_id)
    existing_id = str(submission.get("owner_algorithm_id") or "").strip()
    task_type = str(submission.get("task_type") or "").strip().lower()
    ready = bool(runtime_ready)
    dependency_text = str(submission.get("dependency_text") or "").strip()
    entry_text = str(submission.get("entry_text") or "").strip()
    archive_filename = str(submission.get("archive_filename") or "")
    archive_sha256 = str(submission.get("archive_sha256") or "")
    archive_path = str(submission.get("archive_path") or "")

    if existing_id:
        existing = load_algorithm(r, existing_id)
        if existing and _is_submission_owner_runtime_algorithm(existing, submission_id, owner_id):
            existing["task"] = TASK_LABEL_BY_TYPE.get(task_type, existing.get("task"))
            existing["name"] = _make_owner_unique_algorithm_name(
                r,
                owner_id,
                str(submission.get("name") or existing.get("name") or existing_id).strip() or existing_id,
                exclude_id=existing_id,
                ignore_submission_id=submission_id,
            )
            existing["impl"] = "UserPackage"
            existing["version"] = str(submission.get("version") or existing.get("version") or "v1").strip() or "v1"
            existing["description"] = str(submission.get("description") or existing.get("description") or "")
            existing["visibility"] = "private"
            existing["allow_use"] = ready
            existing["allow_download"] = False
            existing["is_active"] = ready
            existing["runtime_ready"] = ready
            existing["source_submission_id"] = submission_id
            existing["source_owner_id"] = owner_id
            existing["package_role"] = "owner_runtime"
            existing["dependency_text"] = dependency_text
            existing["entry_text"] = entry_text
            existing["archive_filename"] = archive_filename
            existing["archive_sha256"] = archive_sha256
            existing["archive_path"] = archive_path
            save_algorithm(r, existing_id, existing)
            return existing_id

    algorithm_id = _make_unique_algorithm_id(r, f"submission_{submission_id}", owner_id)
    data = {
        "algorithm_id": algorithm_id,
        "task": TASK_LABEL_BY_TYPE.get(task_type, ""),
        "name": _make_owner_unique_algorithm_name(
            r,
            owner_id,
            str(submission.get("name") or submission_id).strip() or submission_id,
            ignore_submission_id=submission_id,
        ),
        "impl": "UserPackage",
        "version": str(submission.get("version") or "v1").strip() or "v1",
        "description": str(submission.get("description") or ""),
        "owner_id": owner_id,
        "created_at": time.time(),
        "default_params": {},
        "param_presets": {},
        "visibility": "private",
        "allow_use": ready,
        "allow_download": False,
        "is_active": ready,
        "runtime_ready": ready,
        "download_count": 0,
        "source_submission_id": submission_id,
        "source_owner_id": owner_id,
        "package_role": "owner_runtime",
        "dependency_text": dependency_text,
        "entry_text": entry_text,
        "archive_filename": archive_filename,
        "archive_sha256": archive_sha256,
        "archive_path": archive_path,
    }
    save_algorithm(r, algorithm_id, data)
    return algorithm_id


def _publish_algorithm_submission_to_community(r, submission: dict, owner_id: str, community_description: str = "") -> str:
    submission_id = str(submission.get("submission_id") or "").strip()
    if not submission_id:
        err.api_error(400, err.E_HTTP, "submission_id_required")
    existing_id = str(submission.get("community_algorithm_id") or "").strip()
    description = _validate_text_encoding(community_description or "", "algorithm_submission.community_description").strip()
    base_description = description or str(submission.get("description") or "").strip()
    dependency_text = str(submission.get("dependency_text") or "").strip()
    entry_text = str(submission.get("entry_text") or "").strip()
    final_description = base_description or "用户已审核通过的算法代码包，后续执行仍走平台受控接入流程。"

    if existing_id:
        existing = load_algorithm(r, existing_id)
        if existing and _is_submission_community_algorithm(existing, submission_id, owner_id):
            existing["task"] = TASK_LABEL_BY_TYPE.get(str(submission.get("task_type") or "").strip().lower(), existing.get("task"))
            existing["name"] = _algorithm_submission_display_name(submission, existing.get("name") or existing_id)
            existing["impl"] = "UserPackage"
            existing["version"] = str(submission.get("version") or existing.get("version") or "v1").strip() or "v1"
            existing["description"] = final_description
            existing["visibility"] = "public"
            existing["allow_use"] = False
            existing["allow_download"] = True
            existing["is_active"] = True
            existing["runtime_ready"] = False
            existing["source_submission_id"] = submission_id
            existing["source_owner_id"] = owner_id
            existing["package_role"] = "community"
            existing["dependency_text"] = dependency_text
            existing["entry_text"] = entry_text
            existing["archive_filename"] = str(submission.get("archive_filename") or "")
            existing["archive_sha256"] = str(submission.get("archive_sha256") or "")
            existing["archive_path"] = str(submission.get("archive_path") or "")
            save_algorithm(r, existing_id, existing)
            return existing_id

    algorithm_id = _make_unique_algorithm_id(r, f"submission_{submission_id}", owner_id)
    name = _algorithm_submission_display_name(submission, submission_id)
    task_type = str(submission.get("task_type") or "").strip().lower()
    data = {
        "algorithm_id": algorithm_id,
        "task": TASK_LABEL_BY_TYPE.get(task_type, ""),
        "name": name,
        "impl": "UserPackage",
        "version": str(submission.get("version") or "v1").strip() or "v1",
        "description": final_description,
        "owner_id": owner_id,
        "created_at": time.time(),
        "default_params": {},
        "param_presets": {},
        "visibility": "public",
        "allow_use": False,
        "allow_download": True,
        "is_active": True,
        "runtime_ready": False,
        "download_count": 0,
        "source_submission_id": submission_id,
        "source_owner_id": owner_id,
        "package_role": "community",
        "dependency_text": dependency_text,
        "entry_text": entry_text,
        "archive_filename": str(submission.get("archive_filename") or ""),
        "archive_sha256": str(submission.get("archive_sha256") or ""),
        "archive_path": str(submission.get("archive_path") or ""),
    }
    save_algorithm(r, algorithm_id, data)
    return algorithm_id


def _list_all_metric_records(r) -> list[dict]:
    return list_metrics(r, limit=5000) or []


def _assert_metric_manage_access(metric: dict, current_user: dict) -> None:
    owner_id = str((metric or {}).get("owner_id") or "").strip() or "system"
    username = _username_of(current_user)
    is_admin = _normalize_user_role(current_user) == "admin"
    if owner_id == username:
        return
    if owner_id == "system" and is_admin:
        return
    if is_admin:
        return
    err.api_error(403, err.E_HTTP, "forbidden_access")


def _list_runnable_metrics(r, task_type: str | None = None) -> list[dict]:
    task_filter = str(task_type or "").strip().lower()
    items = []
    for item in _list_all_metric_records(r):
        if str(item.get("status") or "").lower() != "approved":
            continue
        if not bool(item.get("runtime_ready")):
            continue
        if str(item.get("implementation_type") or "").lower() not in {"builtin", "python"}:
            continue
        task_types = _normalize_metric_task_types(item.get("task_types") if isinstance(item.get("task_types"), list) else [])
        if task_filter and task_types and task_filter not in task_types:
            continue
        items.append(item)
    items.sort(key=lambda x: (str(x.get("owner_id") or "") != "system", str(x.get("display_name") or x.get("name") or x.get("metric_key") or "")))
    return items

def _ensure_catalog_defaults(r):
    """
    纭繚 Redis 涓寘鍚粯璁ょ殑鏁版嵁闆嗗拰绠楁硶銆?    浣跨敤鍏ㄥ眬鍙橀噺缂撳瓨鍒濆鍖栫姸鎬侊紝閬垮厤姣忎釜 API 璇锋眰閮芥墽琛屽鏉傜殑鍒濆鍖栭€昏緫銆?    """
    global _CATALOG_INITIALIZED
    if _CATALOG_INITIALIZED:
        return
    
    # 鎵ц鍒濆鍖栭€昏緫
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
        "name": "Demo-示例数据集",
        "type": demo_type,
        "size": demo_size,
        "owner_id": "system",
        "created_at": created,
        "storage_path": str(demo_ds_dir),
        "meta": demo_meta,
        "task_types": list(TASK_LABEL_BY_TYPE.keys()),
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
        if not isinstance(cur_ds.get("task_types"), list) or not cur_ds.get("task_types"):
            cur_ds["task_types"] = list(TASK_LABEL_BY_TYPE.keys())
            need_patch = True
        if need_patch:
            save_dataset(r, demo_ds_id, cur_ds)

    # 2. 榛樿绠楁硶
    defaults = _builtin_algorithm_catalog()
    for x in defaults:
        cur = load_algorithm(r, x["algorithm_id"])
        if not cur:
            x2 = dict(x)
            x2["created_at"] = created
            x2["owner_id"] = "system"
            save_algorithm(r, x2["algorithm_id"], x2)
            continue
        # 澧為噺淇閫昏緫
        need_patch = False
        if str(cur.get("owner_id") or "") != "system":
            cur["owner_id"] = "system"
            need_patch = True
        if not isinstance(cur.get("created_at"), (int, float)):
            cur["created_at"] = created
            need_patch = True
        if need_patch:
            save_algorithm(r, x["algorithm_id"], cur)

    # 3. 榛樿鎸囨爣
    for item in _builtin_metric_catalog():
        cur = load_metric(r, item["metric_id"])
        if not cur:
            save_metric(r, item["metric_id"], item)
            continue
        need_patch = False
        for key in (
            "metric_key",
            "name",
            "display_name",
            "description",
            "direction",
            "requires_reference",
            "implementation_type",
            "owner_id",
            "status",
            "runtime_ready",
        ):
            if cur.get(key) != item.get(key):
                cur[key] = item.get(key)
                need_patch = True
        if not isinstance(cur.get("task_types"), list) or not cur.get("task_types"):
            cur["task_types"] = item["task_types"]
            need_patch = True
        if not isinstance(cur.get("created_at"), (int, float)):
            cur["created_at"] = item["created_at"]
            need_patch = True
        if need_patch:
            save_metric(r, item["metric_id"], cur)

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


def _dir_contains_files(root: Path) -> bool:
    if not root.exists():
        return False
    for p in root.rglob("*"):
        if p.is_file():
            return True
    return False


def _import_dataset_zip_bytes_into_dir(zip_bytes: bytes, ds_dir: Path, overwrite: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="abp_ds_import_") as tmp_dir:
        stage_dir = Path(tmp_dir) / "stage"
        _safe_extract_zip_bytes(zip_bytes, stage_dir)
        _normalize_dataset_import_layout(stage_dir, overwrite=True)
        if _dir_contains_files(ds_dir) and not overwrite:
            err.api_error(
                409,
                err.E_DATASET_IMPORT_REQUIRES_OVERWRITE,
                "dataset_import_requires_overwrite",
                hint="当前数据集目录已存在文件。若要重新导入并替换现有内容，请勾选“导入时覆盖原有目录内容”。",
                dataset_dir=str(ds_dir),
            )
        if overwrite and ds_dir.exists():
            shutil.rmtree(ds_dir, ignore_errors=True)
        ds_dir.mkdir(parents=True, exist_ok=True)
        _merge_tree(stage_dir, ds_dir, overwrite=True)


def _validate_text_encoding(v: str, field: str) -> str:
    s = (v or "").strip()
    if not s:
        return s
    if "\ufffd" in s or re.search(r"[?锛焆]{3,}", s):
        err.api_error(
            400,
            err.E_TEXT_ENCODING_INVALID,
            "text_encoding_invalid",
            field=field,
            hint="璇蜂娇鐢?UTF-8 鎻愪氦鏂囨湰",
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
    if "\ufffd" in s or re.fullmatch(r"[?锛焆+", s):
        return UNKNOWN_ALGORITHM_TASK_LABEL
    return s


def _get_dataset_cache_key(dataset_id: str) -> str:
    return f"dataset:scan:{dataset_id}"


def _scan_dataset_on_disk(data_root: Path, owner_id: str, dataset_id: str) -> tuple[str, str, dict]:
    # 优先使用用户独立目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 濡傛灉鐢ㄦ埛鐩綍涓嶅瓨鍦紝灏濊瘯浣跨敤鏃х殑鐩綍缁撴瀯锛堢洿鎺ュ湪data涓嬶級
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    gt_dir = ds_dir / "gt"
    if not gt_dir.exists():
        # 妫€鏌ユ槸鍚﹀瓨鍦ㄥ叾浠栧彲鑳界殑GT鐩綍鍚嶇О
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 娌℃湁鎵惧埌GT鐩綍
            return "图像", "0 张", {"supported_task_types": [], "pairs_by_task": {}, "counts_by_dir": {}}
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


def _owner_display_name(r, owner_id: str | None, cache: dict[str, str] | None = None) -> str:
    owner = str(owner_id or "").strip() or "system"
    if cache is not None and owner in cache:
        return cache[owner]
    if owner == "system":
        name = "系统"
    else:
        user = load_user(r, owner) or {}
        name = str(user.get("display_name") or user.get("username") or owner).strip() or owner
    if cache is not None:
        cache[owner] = name
    return name


def _with_owner_display_name(r, item: dict | None, cache: dict[str, str] | None = None) -> dict:
    data = dict(item or {})
    data["owner_display_name"] = _owner_display_name(r, data.get("owner_id"), cache=cache)
    return data


def _sql_record_list(record_type: str, limit: int = 5000) -> Optional[list[dict]]:
    if not sql_store.is_enabled():
        return None
    try:
        return sql_store.list_records(record_type, limit=limit, filter_by_owner=False) or []
    except Exception:
        if not sql_store.allow_redis_fallback():
            raise
        return None


def _sql_record_load(record_type: str, record_id: str) -> Optional[dict]:
    if not sql_store.is_enabled():
        return None
    try:
        return sql_store.load_record(record_type, record_id)
    except Exception:
        if not sql_store.allow_redis_fallback():
            raise
        return None


def _sql_record_save(record_type: str, record_id: str, data: dict) -> None:
    if not sql_store.is_enabled():
        return
    try:
        sql_store.save_record(record_type, record_id, data)
    except Exception:
        if not sql_store.allow_redis_fallback():
            raise


def _sql_record_delete(record_type: str, record_id: str) -> None:
    if not sql_store.is_enabled():
        return
    try:
        sql_store.delete_record(record_type, record_id)
    except Exception:
        if not sql_store.allow_redis_fallback():
            raise


def _merge_by(items: list[dict], sql_items: Optional[list[dict]], key_builder) -> list[dict]:
    if sql_items is None:
        return items
    merged: dict[str, dict] = {}
    for item in items:
        if isinstance(item, dict):
            merged[str(key_builder(item))] = item
    for item in sql_items:
        if isinstance(item, dict):
            merged[str(key_builder(item))] = item
    return list(merged.values())


def _comment_key(resource_type: str, resource_id: str, comment_id: str) -> str:
    return f"comment:{resource_type}:{resource_id}:{comment_id}"


def _comment_record_id(resource_type: str, resource_id: str, comment_id: str) -> str:
    return f"{resource_type}:{resource_id}:{comment_id}"


def _list_resource_comments(r, resource_type: str, resource_id: str) -> list[dict]:
    sql_items = _sql_record_list("comment", limit=5000)
    if sql_items is not None:
        sql_items = [
            item for item in sql_items
            if str(item.get("resource_type") or "") == resource_type and str(item.get("resource_id") or "") == resource_id
        ]
        if not sql_store.allow_redis_fallback():
            sql_items.sort(key=lambda item: float(item.get("created_at") or 0))
            return sql_items
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
    items = _merge_by(items, sql_items, lambda item: _comment_record_id(
        str(item.get("resource_type") or resource_type),
        str(item.get("resource_id") or resource_id),
        str(item.get("comment_id") or ""),
    ))
    items.sort(key=lambda item: float(item.get("created_at") or 0))
    return items


def _save_resource_comment(r, resource_type: str, resource_id: str, data: dict) -> None:
    comment_id = str(data.get("comment_id") or "").strip()
    if not comment_id:
        raise ValueError("comment_id_required")
    _sql_record_save("comment", _comment_record_id(resource_type, resource_id, comment_id), data)
    r.set(_comment_key(resource_type, resource_id, comment_id), json.dumps(data, ensure_ascii=False))


def _load_resource_comment(r, resource_type: str, resource_id: str, comment_id: str) -> Optional[dict]:
    item = _sql_record_load("comment", _comment_record_id(resource_type, resource_id, comment_id))
    if item is not None:
        return item
    if sql_store.is_enabled() and not sql_store.allow_redis_fallback():
        return None
    raw = r.get(_comment_key(resource_type, resource_id, comment_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _delete_resource_comment(r, resource_type: str, resource_id: str, comment_id: str) -> None:
    _sql_record_delete("comment", _comment_record_id(resource_type, resource_id, comment_id))
    r.delete(_comment_key(resource_type, resource_id, comment_id))


def _notice_key(username: str, notice_id: str) -> str:
    return f"notice:{username}:{notice_id}"


def _notice_record_id(username: str, notice_id: str) -> str:
    return f"{username}:{notice_id}"


def _report_key(report_id: str) -> str:
    return f"report:{report_id}"


def _save_notice(r, username: str, data: dict) -> None:
    notice_id = str(data.get("notice_id") or "").strip()
    owner = str(username or "").strip()
    if not notice_id or not owner:
        raise ValueError("notice_key_required")
    _sql_record_save("notice", _notice_record_id(owner, notice_id), data)
    r.set(_notice_key(owner, notice_id), json.dumps(data, ensure_ascii=False))


def _load_notice(r, username: str, notice_id: str) -> Optional[dict]:
    item = _sql_record_load("notice", _notice_record_id(username, notice_id))
    if item is not None:
        return item
    if sql_store.is_enabled() and not sql_store.allow_redis_fallback():
        return None
    raw = r.get(_notice_key(username, notice_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _delete_notice(r, username: str, notice_id: str) -> None:
    owner = str(username or "").strip()
    nid = str(notice_id or "").strip()
    if not owner or not nid:
        return
    _sql_record_delete("notice", _notice_record_id(owner, nid))
    r.delete(_notice_key(owner, nid))


def _list_notices(r, username: str, unread_only: bool = False) -> list[dict]:
    owner = str(username or "").strip()
    if not owner:
        return []
    sql_items = _sql_record_list("notice", limit=5000)
    if sql_items is not None:
        sql_items = [item for item in sql_items if str(item.get("username") or "") == owner]
        if unread_only:
            sql_items = [item for item in sql_items if not bool(item.get("read"))]
        if not sql_store.allow_redis_fallback():
            sql_items.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
            return sql_items
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
    items = _merge_by(items, sql_items, lambda item: _notice_record_id(
        str(item.get("username") or owner),
        str(item.get("notice_id") or ""),
    ))
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
        "title": str(title or "").strip() or "绯荤粺閫氱煡",
        "content": str(content or "").strip(),
        "created_at": time.time(),
        "read": False,
    }
    _save_notice(r, owner, data)
    return data


def _save_report(r, report_id: str, data: dict) -> None:
    _sql_record_save("report", report_id, data)
    r.set(_report_key(report_id), json.dumps(data, ensure_ascii=False))


def _load_report(r, report_id: str) -> Optional[dict]:
    item = _sql_record_load("report", report_id)
    if item is not None:
        return item
    if sql_store.is_enabled() and not sql_store.allow_redis_fallback():
        return None
    raw = r.get(_report_key(report_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _list_reports(r) -> list[dict]:
    sql_items = _sql_record_list("report", limit=5000)
    if sql_items is not None and not sql_store.allow_redis_fallback():
        sql_items.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
        return sql_items
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
    items = _merge_by(items, sql_items, lambda item: str(item.get("report_id") or ""))
    items.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
    return items


def _delete_report(r, report_id: str) -> None:
    _sql_record_delete("report", report_id)
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
    # 先清理关联 Run，避免任务中心残留「已删除算法」的历史任务条目。
    for run in list_all_runs(r, limit=50000) or []:
        run_id = str(run.get("run_id") or "").strip()
        if not run_id:
            continue
        if str(run.get("algorithm_id") or "").strip() != algorithm_id:
            continue
        try:
            r.set(f"run_cancel:{run_id}", "1", ex=3600)
        except Exception:
            pass
        delete_run(r, run_id)
    delete_algorithm(r, algorithm_id)
    owner_id = str((algorithm or {}).get("owner_id") or "").strip()
    if owner_id:
        for preset in list_presets(r, limit=5000, owner_id=owner_id) or []:
            preset_primary_algorithm_id = str(preset.get("algorithm_id") or "").strip()
            preset_algorithm_ids = [
                str(x or "").strip()
                for x in (preset.get("algorithm_ids") or [])
                if str(x or "").strip()
            ]
            if (
                preset_primary_algorithm_id == algorithm_id
                or algorithm_id in preset_algorithm_ids
            ):
                delete_preset(r, str(preset.get("preset_id") or ""))


def _delete_algorithm_submission_by_record(r, cur: dict) -> None:
    """删除一条接入申请及其关联用户侧算法、磁盘包（与 DELETE /algorithm-submissions/{id} 一致）。"""
    submission_id = str(cur.get("submission_id") or "").strip()
    if not submission_id:
        return
    community_algorithm_id = str(cur.get("community_algorithm_id") or "").strip()
    if community_algorithm_id:
        community_algorithm = load_algorithm(r, community_algorithm_id)
        if community_algorithm and str(community_algorithm.get("owner_id") or "") == str(cur.get("owner_id") or ""):
            _delete_algorithm_record_with_related_state(r, community_algorithm)
    owner_algorithm_id = str(cur.get("owner_algorithm_id") or "").strip()
    if owner_algorithm_id:
        owner_algorithm = load_algorithm(r, owner_algorithm_id)
        if owner_algorithm and str(owner_algorithm.get("owner_id") or "") == str(cur.get("owner_id") or ""):
            _delete_algorithm_record_with_related_state(r, owner_algorithm)

    delete_algorithm_submission(r, submission_id)
    has_archive_reference = False
    for data in _list_all_algorithm_records(r):
        if not isinstance(data, dict):
            continue
        if str(data.get("source_submission_id") or "").strip() == submission_id:
            has_archive_reference = True
            break
    if not str(cur.get("platform_algorithm_id") or "").strip() and not has_archive_reference:
        try:
            shutil.rmtree(_algorithm_submission_dir(str(cur.get("owner_id") or "system"), submission_id), ignore_errors=True)
        except Exception:
            pass


def _purge_user_algorithm_library(r, target_username: str) -> dict[str, int]:
    """删除某用户名下所有接入申请与用户算法（不含平台内置）。"""
    target_username = str(target_username or "").strip()
    _ensure_catalog_defaults(r)
    removed_submissions = 0
    subs = [
        s
        for s in (_list_all_algorithm_submissions(r) or [])
        if str(s.get("owner_id") or "").strip() == target_username
    ]
    for cur in subs:
        if not isinstance(cur, dict):
            continue
        _delete_algorithm_submission_by_record(r, cur)
        removed_submissions += 1

    removed_algorithms = 0
    for x in list_algorithms(r, limit=5000, owner_id=target_username, include_public=True) or []:
        if not isinstance(x, dict):
            continue
        aid = str(x.get("algorithm_id") or "").strip()
        if not aid or aid in BUILTIN_ALGORITHM_IDS:
            continue
        if str(x.get("owner_id") or "").strip() != target_username:
            continue
        _delete_algorithm_record_with_related_state(r, x)
        removed_algorithms += 1

    _ensure_catalog_defaults(r)
    return {"removed_submissions": removed_submissions, "removed_algorithms": removed_algorithms}


def _delete_metric_record_with_related_state(r, metric: dict) -> None:
    metric_id = str((metric or {}).get("metric_id") or "").strip()
    if not metric_id:
        return
    delete_metric(r, metric_id)


def _remove_algorithm_download_copies(
    r,
    *,
    source_algorithm_id: str,
    source_owner_id: str,
    notice_title: str = "",
    notice_message: str = "",
) -> list[str]:
    source_algorithm_id = str(source_algorithm_id or "").strip()
    source_owner_id = str(source_owner_id or "").strip()
    if not source_algorithm_id or not source_owner_id:
        return []
    affected_users: list[str] = []
    for item in list(_list_all_algorithm_records(r)):
        item_owner = str(item.get("owner_id") or "").strip()
        if item_owner in {"", "system", source_owner_id}:
            continue
        if str(item.get("source_algorithm_id") or "").strip() != source_algorithm_id:
            continue
        if str(item.get("source_owner_id") or "").strip() != source_owner_id:
            continue
        _delete_algorithm_record_with_related_state(r, item)
        if item_owner:
            affected_users.append(item_owner)
            if notice_title and notice_message:
                _create_notice(r, item_owner, notice_title, notice_message, kind="warning")
    return affected_users


def _remove_dataset_download_copies(
    r,
    *,
    source_dataset_id: str,
    source_owner_id: str,
    notice_title: str = "",
    notice_message: str = "",
) -> list[str]:
    source_dataset_id = str(source_dataset_id or "").strip()
    source_owner_id = str(source_owner_id or "").strip()
    if not source_dataset_id or not source_owner_id:
        return []
    affected_users: list[str] = []
    for item in list(_list_all_dataset_records(r)):
        item_owner = str(item.get("owner_id") or "").strip()
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        item_source_dataset_id = str(item.get("source_dataset_id") or meta.get("downloaded_from_dataset_id") or "").strip()
        item_source_owner_id = str(item.get("source_owner_id") or meta.get("downloaded_from_owner_id") or "").strip()
        if item_owner in {"", "system", source_owner_id}:
            continue
        if item_source_dataset_id != source_dataset_id or item_source_owner_id != source_owner_id:
            continue
        _delete_dataset_record_with_related_state(r, item, delete_disk=True)
        if item_owner:
            affected_users.append(item_owner)
            if notice_title and notice_message:
                _create_notice(r, item_owner, notice_title, notice_message, kind="warning")
    return affected_users


def _remove_metric_download_copies(
    r,
    *,
    source_metric_id: str,
    source_owner_id: str,
    notice_title: str = "",
    notice_message: str = "",
) -> list[str]:
    source_metric_id = str(source_metric_id or "").strip()
    source_owner_id = str(source_owner_id or "").strip()
    if not source_metric_id or not source_owner_id:
        return []
    affected_users: list[str] = []
    for item in list(_list_all_metric_records(r)):
        item_owner = str(item.get("owner_id") or "").strip()
        if item_owner in {"", "system", source_owner_id}:
            continue
        if str(item.get("source_metric_id") or "").strip() != source_metric_id:
            continue
        if str(item.get("source_owner_id") or "").strip() != source_owner_id:
            continue
        _delete_metric_record_with_related_state(r, item)
        if item_owner:
            affected_users.append(item_owner)
            if notice_title and notice_message:
                _create_notice(r, item_owner, notice_title, notice_message, kind="warning")
    return affected_users


def _purge_submission_related_algorithms(r, submission: dict, *, keep_algorithm_ids: set[str] | None = None) -> list[str]:
    submission_id = str((submission or {}).get("submission_id") or "").strip()
    if not submission_id:
        return []
    keep = {str(x).strip() for x in (keep_algorithm_ids or set()) if str(x).strip()}
    affected_users: list[str] = []
    for item in list(_list_all_algorithm_records(r)):
        algorithm_id = str(item.get("algorithm_id") or "").strip()
        if algorithm_id in keep:
            continue
        if str(item.get("owner_id") or "").strip() == "system":
            continue
        if str(item.get("source_submission_id") or "").strip() != submission_id:
            continue
        item_owner = str(item.get("owner_id") or "").strip()
        _delete_algorithm_record_with_related_state(r, item)
        if item_owner:
            affected_users.append(item_owner)
    return affected_users


def _reconcile_algorithm_records(r) -> None:
    submissions = _list_all_algorithm_submissions(r)
    algorithms = _list_all_algorithm_records(r)
    system_platform_by_submission_id: dict[str, str] = {}
    for item in algorithms:
        if str(item.get("owner_id") or "").strip() != "system":
            continue
        submission_id = str(item.get("source_submission_id") or "").strip()
        if not submission_id:
            continue
        system_platform_by_submission_id.setdefault(submission_id, str(item.get("algorithm_id") or "").strip())

    for submission in submissions:
        submission_id = str(submission.get("submission_id") or "").strip()
        if not submission_id:
            continue
        desired_name = _algorithm_submission_display_name(submission, submission_id)
        platform_algorithm_id = str(submission.get("platform_algorithm_id") or "").strip()
        if not platform_algorithm_id:
            platform_algorithm_id = system_platform_by_submission_id.get(submission_id, "")
        platform_algorithm = load_algorithm(r, platform_algorithm_id) if platform_algorithm_id else None
        if platform_algorithm and str(platform_algorithm.get("owner_id") or "").strip() == "system":
            removed_users = _purge_submission_related_algorithms(r, submission, keep_algorithm_ids={platform_algorithm_id})
            changed = False
            if str(submission.get("platform_algorithm_id") or "").strip() != platform_algorithm_id:
                submission["platform_algorithm_id"] = platform_algorithm_id
                changed = True
            if str(submission.get("owner_algorithm_id") or "").strip():
                submission["owner_algorithm_id"] = None
                changed = True
            if str(submission.get("community_algorithm_id") or "").strip():
                submission["community_algorithm_id"] = None
                changed = True
            if changed:
                save_algorithm_submission(r, submission_id, submission)
            source_name = desired_name or platform_algorithm_id
            for user_id in sorted({x for x in removed_users if x and x != str(submission.get("owner_id") or "").strip()}):
                _create_notice(
                    r,
                    user_id,
                    "关联算法已切换为平台算法",
                    f"你下载或持有的算法“{source_name}”已被平台收录，旧副本已清理，请直接使用平台算法。",
                    kind="info",
                )
            continue

        for item in list(_list_all_algorithm_records(r)):
            if str(item.get("owner_id") or "").strip() == "system":
                continue
            if str(item.get("source_submission_id") or "").strip() != submission_id:
                continue
            if str(item.get("name") or "").strip() == desired_name:
                continue
            current_name = str(item.get("name") or "").strip()
            if current_name == desired_name or re.fullmatch(rf"{re.escape(desired_name)}\s+#\d+", current_name):
                item["name"] = desired_name
                save_algorithm(r, str(item.get("algorithm_id") or "").strip(), item)

    algorithms = _list_all_algorithm_records(r)
    for item in algorithms:
        if str(item.get("owner_id") or "").strip() != "system":
            continue
        source_algorithm_id = str(item.get("source_algorithm_id") or "").strip()
        source_owner_id = str(item.get("source_owner_id") or "").strip()
        if not source_algorithm_id or not source_owner_id or source_owner_id == "system":
            continue
        if str(item.get("source_submission_id") or "").strip():
            continue
        source = load_algorithm(r, source_algorithm_id)
        if source and str(source.get("owner_id") or "").strip() == source_owner_id:
            _delete_algorithm_record_with_related_state(r, source)
        _remove_algorithm_download_copies(r, source_algorithm_id=source_algorithm_id, source_owner_id=source_owner_id)

    for item in list(_list_all_algorithm_records(r)):
        source_algorithm_id = str(item.get("source_algorithm_id") or "").strip()
        source_owner_id = str(item.get("source_owner_id") or "").strip()
        if not source_algorithm_id or not source_owner_id:
            continue
        source = load_algorithm(r, source_algorithm_id)
        if not source or str(source.get("owner_id") or "").strip() != source_owner_id:
            continue
        desired_name = str(source.get("name") or "").strip()
        current_name = str(item.get("name") or "").strip()
        if not desired_name or current_name == desired_name:
            changed = False
        elif re.fullmatch(rf"{re.escape(desired_name)}\s+#\d+", current_name):
            item["name"] = desired_name
            changed = True
        else:
            changed = False
        if _infer_user_package_role(item) == "downloaded_community":
            expected_runtime_ready = _is_userpackage_download_runtime_ready(item)
            if bool(item.get("runtime_ready")) != expected_runtime_ready:
                item["runtime_ready"] = expected_runtime_ready
                changed = True
            if item.get("is_active") is False:
                item["is_active"] = True
                changed = True
        if changed:
            save_algorithm(r, str(item.get("algorithm_id") or "").strip(), item)

    for item in list(_list_all_algorithm_records(r)):
        if str(item.get("owner_id") or "").strip() == "system":
            continue
        source_algorithm_id = str(item.get("source_algorithm_id") or "").strip()
        source_owner_id = str(item.get("source_owner_id") or "").strip()
        if not source_algorithm_id or not source_owner_id:
            continue
        source = load_algorithm(r, source_algorithm_id)
        if source_owner_id == "system":
            invalid = not source or str(source.get("owner_id") or "").strip() != "system" or not _is_algorithm_active(source)
        else:
            invalid = (
                not source
                or str(source.get("owner_id") or "").strip() != source_owner_id
                or str(source.get("visibility") or "private").strip().lower() != "public"
                or not bool(source.get("allow_download"))
            )
        if invalid:
            _delete_algorithm_record_with_related_state(r, item)


def _reconcile_dataset_records(r) -> None:
    for item in list(_list_all_dataset_records(r)):
        if str(item.get("owner_id") or "").strip() == "system":
            continue
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        source_dataset_id = str(item.get("source_dataset_id") or meta.get("downloaded_from_dataset_id") or "").strip()
        source_owner_id = str(item.get("source_owner_id") or meta.get("downloaded_from_owner_id") or "").strip()
        if not source_dataset_id or not source_owner_id:
            continue
        source = load_dataset(r, source_dataset_id)
        invalid = (
            not source
            or str(source.get("owner_id") or "").strip() != source_owner_id
            or str(source.get("visibility") or "private").strip().lower() != "public"
            or not bool(source.get("allow_download"))
            or not _dataset_has_files(_dataset_dir_from_record(source))
        )
        if invalid:
            _delete_dataset_record_with_related_state(r, item, delete_disk=True)


def _reconcile_metric_records(r) -> None:
    for item in list(_list_all_metric_records(r)):
        if str(item.get("owner_id") or "").strip() == "system":
            continue
        source_metric_id = str(item.get("source_metric_id") or "").strip()
        source_owner_id = str(item.get("source_owner_id") or "").strip()
        if not source_metric_id or not source_owner_id:
            continue
        source = load_metric(r, source_metric_id)
        invalid = (
            not source
            or str(source.get("owner_id") or "").strip() != source_owner_id
            or str(source.get("visibility") or "private").strip().lower() != "public"
            or not bool(source.get("allow_download"))
            or str(source.get("status") or "").strip().lower() != "approved"
        )
        if invalid:
            _delete_metric_record_with_related_state(r, item)


def _run_reconcile_job(r, name: str, fn, *, min_interval_s: float = 8.0, force: bool = False) -> None:
    job_name = str(name or "").strip().lower()
    if not job_name:
        return
    now = time.time()
    key = f"reconcile_job:{job_name}"
    if not force:
        try:
            last_raw = r.get(key)
            last_ts = float(last_raw) if last_raw is not None else 0.0
        except Exception:
            last_ts = 0.0
        if last_ts > 0 and (now - last_ts) < float(min_interval_s):
            return
    fn(r)
    try:
        r.set(key, str(now))
    except Exception:
        pass


def _metric_key_available_for_owner(r, owner_id: str, metric_key: str) -> bool:
    wanted = str(metric_key or "").strip().upper()
    if not wanted:
        return False
    if wanted in {"PSNR", "SSIM", "NIQE"}:
        return True
    for item in _list_all_metric_records(r):
        item_owner = str(item.get("owner_id") or "").strip() or "system"
        if item_owner not in {"system", str(owner_id or "").strip()}:
            continue
        if str(item.get("metric_key") or "").strip().upper() != wanted:
            continue
        if str(item.get("status") or "").strip().lower() != "approved":
            continue
        if not bool(item.get("runtime_ready")):
            continue
        return True
    return False


def _cleanup_invalid_runs_for_owner(r, owner_id: str | None) -> None:
    owner = str(owner_id or "").strip()
    if not owner:
        return
    for run in list_runs(r, limit=5000, owner_id=owner) or []:
        run_id = str(run.get("run_id") or "").strip()
        if not run_id:
            continue
        if str(run.get("owner_id") or "").strip() != owner:
            continue
        algorithm_id = str(run.get("algorithm_id") or "").strip()
        dataset_id = str(run.get("dataset_id") or "").strip()
        algorithm = load_algorithm(r, algorithm_id) if algorithm_id else None
        dataset = load_dataset(r, dataset_id) if dataset_id else None
        metrics = []
        if isinstance(run.get("params"), dict) and isinstance(run["params"].get("metrics"), list):
            metrics = [str(x).strip() for x in run["params"].get("metrics") if str(x).strip()]
        invalid = not algorithm or not dataset
        if not invalid:
            for metric_key in metrics:
                if not _metric_key_available_for_owner(r, owner, metric_key):
                    invalid = True
                    break
        if invalid:
            delete_run(r, run_id)


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


def _dataset_is_publicly_available(dataset: dict | None) -> bool:
    if not isinstance(dataset, dict):
        return False
    if not bool(dataset.get("allow_download")):
        return False
    if str(dataset.get("visibility") or "private").strip().lower() != "public":
        return False
    return _dataset_has_files(_dataset_dir_from_record(dataset))


def _list_all_dataset_records(r) -> list[dict]:
    return list_all_datasets(r, limit=5000) or []


def _list_all_algorithm_records(r) -> list[dict]:
    return list_all_algorithms(r, limit=5000) or []


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
    return algorithm.get("is_active") is not False


def _normalize_algorithm_runtime_state(algorithm: dict | None) -> dict:
    if not isinstance(algorithm, dict):
        return {}
    item = dict(algorithm)
    impl = str(item.get("impl") or "").strip().lower()
    owner_id = str(item.get("owner_id") or "system").strip() or "system"
    if impl == "userpackage":
        role = _infer_user_package_role(item)
        if role:
            item["package_role"] = role
        allow_use = bool(item.get("allow_use", False))
        if role == "platform" or owner_id == "system":
            if item.get("runtime_ready") is None:
                item["runtime_ready"] = allow_use
            if item.get("is_active") is None:
                item["is_active"] = allow_use
            item["package_role"] = "platform"
        elif role == "owner_runtime":
            if item.get("runtime_ready") is None:
                item["runtime_ready"] = allow_use
            if item.get("is_active") is None:
                item["is_active"] = bool(item.get("runtime_ready"))
            item["visibility"] = "private"
            item["allow_download"] = False
            item["package_role"] = "owner_runtime"
            if not str(item.get("source_owner_id") or "").strip():
                item["source_owner_id"] = owner_id
        elif role == "community":
            item["runtime_ready"] = False
            if item.get("is_active") is None:
                item["is_active"] = True
            item["allow_use"] = False
            item["allow_download"] = True
            item["package_role"] = "community"
            if not str(item.get("source_owner_id") or "").strip():
                item["source_owner_id"] = owner_id
        elif role == "downloaded_community":
            item["allow_use"] = True
            item["runtime_ready"] = _is_userpackage_download_runtime_ready(item)
            if item.get("is_active") is None:
                item["is_active"] = True
            item["package_role"] = "downloaded_community"
    return item


def _assert_algorithm_manage_access(algorithm: dict, current_user: dict) -> None:
    owner_id = str((algorithm or {}).get("owner_id") or "system").strip() or "system"
    if owner_id == "system":
        _require_admin(current_user)
        return
    _assert_resource_access(algorithm, current_user, allow_system=False)


def _list_all_runs(r, limit: int = 5000) -> list[dict]:
    return list_all_runs(r, limit=limit) or []


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
    sql_items = _sql_record_list("comment", limit=5000)
    if sql_items is not None and not sql_store.allow_redis_fallback():
        sql_items.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
        return sql_items
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
    items = _merge_by(items, sql_items, lambda item: _comment_record_id(
        str(item.get("resource_type") or ""),
        str(item.get("resource_id") or ""),
        str(item.get("comment_id") or ""),
    ))
    items.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
    return items


def _assert_pinned_user(current_user: dict) -> None:
    if _username_of(current_user) != _PINNED_OWNER_USERNAME:
        err.api_error(403, err.E_HTTP, "forbidden_access")


@app.get("/datasets")
def get_datasets(limit: int = 200, scope: str = Query("manage"), current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    _run_reconcile_job(r, "datasets", _reconcile_dataset_records)
    # 绠＄悊椤靛彧杩斿洖褰撳墠鐢ㄦ埛鑷繁鐨勬暟鎹泦锛涚ぞ鍖洪〉鍗曠嫭杩斿洖鍏紑璧勬簮
    owner_id = _username_of(current_user) or None
    include_public = str(scope or "manage").lower() == "community"
    owner_name_cache: dict[str, str] = {}
    if include_public:
        owner_id = None
        # 多取候选再按 load_dataset 校准，避免 SQL 列表与 Redis 不一致时出现「已下架仍展示」
        pool_limit = max(int(limit or 200) * 4, 400)
        items = list_datasets(r, limit=pool_limit, owner_id=owner_id, include_public=True)
        out: list = []
        seen: set[str] = set()
        for it in sorted(items, key=lambda x: float(x.get("created_at") or 0), reverse=True):
            did = str(it.get("dataset_id") or "").strip()
            if not did or did in seen:
                continue
            cur = load_dataset(r, did)
            if not cur:
                continue
            if str(cur.get("owner_id") or "").strip().lower() == "system":
                continue
            if not _dataset_is_publicly_available(cur):
                continue
            out.append(_with_owner_display_name(r, cur, cache=owner_name_cache))
            seen.add(did)
            if len(out) >= int(limit or 200):
                break
        return out

    if not owner_id:
        return []

    items = list_datasets(r, limit=limit, owner_id=owner_id, include_public=False)
    filtered = [item for item in items if str(item.get("owner_id") or "") == owner_id][:limit]
    return [_with_owner_display_name(r, item, cache=owner_name_cache) for item in filtered]


@app.post("/datasets", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    owner_id = _username_of(current_user)
    dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
    visibility = _normalize_visibility(payload.visibility)
    allow_use = visibility == "public"
    allow_download = visibility == "public"
    task_types = _normalize_dataset_task_types(payload.task_types)
    existing_dataset = None
    
    if existing_dataset:
        # 妫€鏌ユ暟鎹泦鏄惁灞炰簬褰撳墠鐢ㄦ埛
        if str(existing_dataset.get("owner_id")) != owner_id:
            err.api_error(409, err.E_DATASET_ID_EXISTS, "dataset_id_exists", dataset_id=dataset_id)
        # 如果是当前用户的数据集，则更新原记录
        data = {
            **existing_dataset,
            "name": _validate_text_encoding(payload.name, "dataset.name"),
            "type": _validate_text_encoding(payload.type, "dataset.type"),
            "size": _validate_text_encoding(payload.size, "dataset.size"),
            "description": _validate_text_encoding(payload.description, "dataset.description"),
            "visibility": visibility,
            "allow_use": allow_use,
            "allow_download": allow_download,
            "task_types": task_types,
        }
    else:
        # 鍒涘缓鏂版暟鎹泦
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
            "task_types": task_types,
        }
    
    save_dataset(r, dataset_id, data)
    _require_task_types_for_user_public_dataset(data)
    return DatasetOut(**data)


@app.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def patch_dataset(dataset_id: str, payload: DatasetPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_dataset(r, dataset_id)
    if not cur:
        err.api_error(404, err.E_DATASET_NOT_FOUND, "dataset_not_found", dataset_id=dataset_id)
    
    _assert_resource_access(cur, current_user, allow_system=True)
        
    was_public = str(cur.get("visibility", "private")).strip().lower() == "public"
    if payload.name is not None:
        cur["name"] = _validate_text_encoding(payload.name, "dataset.name")
    if payload.type is not None:
        cur["type"] = _validate_text_encoding(payload.type, "dataset.type")
    if payload.size is not None:
        cur["size"] = _validate_text_encoding(payload.size, "dataset.size")
    if payload.description is not None:
        cur["description"] = _validate_text_encoding(payload.description, "dataset.description")
    if payload.task_types is not None:
        cur["task_types"] = _normalize_dataset_task_types(payload.task_types)
    if payload.visibility is not None:
        cur["visibility"] = _normalize_visibility(payload.visibility)
        if str(cur.get("visibility", "private")) == "public" and not _dataset_has_files(_dataset_dir_from_record(cur)):
            err.api_error(400, err.E_HTTP, "empty_dataset_not_allowed", dataset_id=dataset_id)
    _require_task_types_for_user_public_dataset(cur)
    is_public = str(cur.get("visibility", "private")) == "public"
    cur["allow_use"] = is_public
    cur["allow_download"] = is_public
    if not isinstance(cur.get("meta"), dict):
        cur["meta"] = {}
    save_dataset(r, dataset_id, cur)
    if was_public and not is_public and str(cur.get("owner_id") or "").strip() != "system":
        source_name = str(cur.get("name") or dataset_id).strip() or dataset_id
        _remove_dataset_download_copies(
            r,
            source_dataset_id=dataset_id,
            source_owner_id=str(cur.get("owner_id") or "").strip(),
            notice_title="社区数据集已下架",
            notice_message=f"你下载的社区数据集“{source_name}”已被发布者下架，副本已从你的数据集库中移除。",
        )
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
    owner_id = str(cur.get("owner_id") or "").strip()
    source_dataset_id = str(cur.get("source_dataset_id") or "").strip()
    if owner_id and owner_id != "system" and not source_dataset_id:
        source_name = str(cur.get("name") or dataset_id).strip() or dataset_id
        _remove_dataset_download_copies(
            r,
            source_dataset_id=dataset_id,
            source_owner_id=owner_id,
            notice_title="社区数据集已删除",
            notice_message=f"你下载的社区数据集“{source_name}”已被发布者删除，副本已从你的数据集库中移除。",
        )
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
        headers=_attachment_headers(filename),
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
    if not _dataset_has_files(_dataset_dir_from_record(source)):
        if source_owner != "system" and visibility == "public":
            source["visibility"] = "private"
            source["allow_use"] = False
            source["allow_download"] = False
            save_dataset(r, dataset_id, source)
            _remove_dataset_download_copies(
                r,
                source_dataset_id=dataset_id,
                source_owner_id=source_owner,
                notice_title="社区数据集已下架",
                notice_message=f"你下载的社区数据集“{str(source.get('name') or dataset_id).strip() or dataset_id}”源文件已失效，副本已从你的数据集库中移除。",
            )
        err.api_error(400, err.E_HTTP, "empty_dataset_not_allowed", dataset_id=dataset_id)

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
    target_dir = _dataset_storage_root() / target_owner / target_dataset_id
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    if source_dir.exists():
        shutil.copytree(source_dir, target_dir)
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
    if not _dataset_has_files(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
        err.api_error(
            500,
            err.E_HTTP,
            "dataset_download_copy_missing_files",
            dataset_id=dataset_id,
            source_dir=str(source_dir),
            target_dir=str(target_dir),
        )

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
    """计算数据集文件系统哈希，用于检测文件变化。"""
    # 优先使用用户独立目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 濡傛灉鐢ㄦ埛鐩綍涓嶅瓨鍦紝灏濊瘯浣跨敤鏃х殑鐩綍缁撴瀯锛堢洿鎺ュ湪data涓嬶級
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    import hashlib
    import os
    
    hasher = hashlib.md5()
    
    if ds_dir.exists():
        # 遍历目录，计算文件路径和修改时间的哈希
        for root, dirs, files in os.walk(ds_dir):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    # 鑾峰彇鏂囦欢淇敼鏃堕棿
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
    force_refresh: bool = Query(False, description="鏄惁寮哄埗鍒锋柊缂撳瓨"),
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
    
    # 濡傛灉鏂囦欢绯荤粺鍙戠敓鍙樺寲锛屽鍔犵増鏈彿
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
            # 只有缓存版本与当前版本一致时才复用
            if cached.get("version") == current_version:
                t = cached.get("type")
                size = cached.get("size")
                meta = cached.get("meta", {})
            else:
                # 鐗堟湰涓嶄竴鑷达紝缂撳瓨澶辨晥
                use_cache = False
        except Exception:
            use_cache = False
    else:
        use_cache = False
    
    # 濡傛灉娌℃湁缂撳瓨鎴栫紦瀛樻棤鏁堬紝鎵ц鎵弿
    if not use_cache:
        data_root = Path(__file__).resolve().parents[1] / "data"
        # 纭繚鏁版嵁鐩綍瀛樺湪
        data_root.mkdir(parents=True, exist_ok=True)
        # 获取数据集所有者
        owner_id = cur.get("owner_id", "system")
        # 使用用户独立目录结构
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
        # 缂撳瓨姘镐笉杩囨湡锛屽彧鏈夊湪鏁版嵁闆嗗彉鍖栨椂鎵嶄細澶辨晥
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
    _apply_task_types_from_scan_meta(cur, meta)
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
            "type": "鍥惧儚",
            "size": "-",
            "storage_path": str(_make_managed_dataset_dir(owner_id, dataset_id)),
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
        }
    else:
        # 浠庣幇鏈夋暟鎹泦涓幏鍙杘wner_id
        owner_id = cur.get("owner_id", _username_of(current_user))
    _assert_resource_access(cur, current_user, allow_system=True)

    try:
        zip_bytes = base64.b64decode(payload.data_b64.encode("utf-8"), validate=True)
    except Exception:
        err.api_error(400, err.E_BAD_BASE64, "bad_base64")

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 使用用户独立目录结构
    user_dir = data_root / owner_id
    # 确保数据目录存在
    ds_dir = _dataset_dir_from_record(cur)
    ds_dir.parent.mkdir(parents=True, exist_ok=True)
    _import_dataset_zip_bytes_into_dir(zip_bytes, ds_dir, overwrite=True)

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
    _apply_task_types_from_scan_meta(cur, meta)
    cur["source_owner_id"] = str(cur.get("source_owner_id") or meta.get("downloaded_from_owner_id") or "") or None
    cur["source_dataset_id"] = str(cur.get("source_dataset_id") or meta.get("downloaded_from_dataset_id") or "") or None
    save_dataset(r, dataset_id, cur)
    
    # 澧炲姞鏁版嵁闆嗙増鏈彿锛屼娇缂撳瓨澶辨晥
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
            "type": "鍥惧儚",
            "size": "-",
            "owner_id": owner_id,
            "created_at": created,
            "meta": {},
        }
    else:
        # 浠庣幇鏈夋暟鎹泦涓幏鍙杘wner_id
        owner_id = cur.get("owner_id", _username_of(current_user))
    _assert_resource_access(cur, current_user, allow_system=True)
    try:
        zip_bytes = file.file.read()
    except Exception:
        err.api_error(400, err.E_BAD_BASE64, "bad_zip_file")

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 使用用户独立目录结构
    user_dir = data_root / owner_id
    # 纭繚鏁版嵁鐩綍瀛樺湪
    ds_dir = _dataset_dir_from_record(cur)
    ds_dir.parent.mkdir(parents=True, exist_ok=True)
    _import_dataset_zip_bytes_into_dir(zip_bytes, ds_dir, overwrite=True)

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
    _apply_task_types_from_scan_meta(cur, meta)
    save_dataset(r, dataset_id, cur)
    
    # 澧炲姞鏁版嵁闆嗙増鏈彿锛屼娇缂撳瓨澶辨晥
    _increment_dataset_version(r, dataset_id)
    
    # 清除缓存，确保下次扫描获取最新数据
    cache_key = _get_dataset_cache_key(dataset_id)
    r.delete(cache_key)
    
    return DatasetOut(**cur)



@app.get("/algorithms")
def get_algorithms(limit: int = 500, scope: str = Query("manage"), current_user: Optional[dict] = Depends(get_current_user_optional)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    _run_reconcile_job(r, "algorithms", _reconcile_algorithm_records)
    include_public = str(scope or "manage").lower() == "community"
    owner_id = None if include_public else (current_user["username"] if current_user else None)
    is_admin = _normalize_user_role(current_user) == "admin"
    catalog = _builtin_algorithm_catalog()
    defaults_by_id = {x["algorithm_id"]: dict(x.get("default_params") or {}) for x in catalog}
    presets_by_id = {x["algorithm_id"]: dict(x.get("param_presets") or {}) for x in catalog}

    _repair_submission_community_algorithm_names(r, owner_id=owner_id if not include_public else None)
    if owner_id and not include_public:
        for submission in _list_all_algorithm_submissions(r):
            if str(submission.get("owner_id") or "").strip() != owner_id:
                continue
            _ensure_submission_owner_algorithm_synced(r, submission)
    items = list_algorithms(r, limit=limit, owner_id=owner_id, include_public=include_public) or []
    out = []
    owner_name_cache: dict[str, str] = {}
    for raw_item in items:
        x = _normalize_algorithm_runtime_state(raw_item)
        alg_id = x.get("algorithm_id")
        if isinstance(alg_id, str) and x != raw_item:
            save_algorithm(r, alg_id, x)
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
        out.append(AlgorithmOut(**_with_owner_display_name(r, x, cache=owner_name_cache)).model_dump())
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
        # 仅允许更新当前用户自己的算法
        if str(existing_algorithm.get("owner_id")) != owner_id:
            err.api_error(409, err.E_ALGORITHM_ID_EXISTS, "algorithm_id_exists", algorithm_id=algorithm_id)
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
        # 创建新算法并确保算法名称唯一
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
        
    was_public = str(cur.get("visibility", "private")).strip().lower() == "public"
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
    if (
        was_public
        and not is_public
        and str(cur.get("owner_id") or "").strip() != "system"
        and not str(cur.get("source_algorithm_id") or "").strip()
    ):
        source_name = str(cur.get("name") or algorithm_id).strip() or algorithm_id
        _remove_algorithm_download_copies(
            r,
            source_algorithm_id=algorithm_id,
            source_owner_id=str(cur.get("owner_id") or "").strip(),
            notice_title="社区算法已下架",
            notice_message=f"你下载的社区算法“{source_name}”已被发布者下架，副本已从你的算法库中移除。",
        )
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

    submission_id = str(cur.get("source_submission_id") or "").strip()
    if submission_id:
        submission = load_algorithm_submission(r, submission_id)
        if (
            submission
            and str(submission.get("owner_id") or "").strip() == owner_id
            and str(submission.get("owner_algorithm_id") or "").strip() == algorithm_id
        ):
            community_algorithm_id = str(submission.get("community_algorithm_id") or "").strip()
            if community_algorithm_id and community_algorithm_id != algorithm_id:
                source_name = str(cur.get("name") or community_algorithm_id).strip() or community_algorithm_id
                _remove_algorithm_download_copies(
                    r,
                    source_algorithm_id=community_algorithm_id,
                    source_owner_id=owner_id,
                    notice_title="社区算法已删除",
                    notice_message=f"你下载的社区算法“{source_name}”已被发布者删除，副本已从你的算法库中移除。",
                )
                community_algorithm = load_algorithm(r, community_algorithm_id)
                if community_algorithm and str(community_algorithm.get("owner_id") or "").strip() == owner_id:
                    _delete_algorithm_record_with_related_state(r, community_algorithm)

            delete_algorithm_submission(r, submission_id)

            has_archive_reference = False
            for data in _list_all_algorithm_records(r):
                if not isinstance(data, dict):
                    continue
                if str(data.get("algorithm_id") or "").strip() == algorithm_id:
                    continue
                if str(data.get("source_submission_id") or "").strip() == submission_id:
                    has_archive_reference = True
                    break

            if not str(submission.get("platform_algorithm_id") or "").strip() and not has_archive_reference:
                try:
                    shutil.rmtree(_algorithm_submission_dir(owner_id, submission_id), ignore_errors=True)
                except Exception:
                    pass

    if owner_id != "system" and not submission_id and not str(cur.get("source_algorithm_id") or "").strip():
        source_name = str(cur.get("name") or algorithm_id).strip() or algorithm_id
        _remove_algorithm_download_copies(
            r,
            source_algorithm_id=algorithm_id,
            source_owner_id=owner_id,
            notice_title="社区算法已删除",
            notice_message=f"你下载的社区算法“{source_name}”已被发布者删除，副本已从你的算法库中移除。",
        )

    _delete_algorithm_record_with_related_state(r, cur)
    return {"ok": True, "algorithm_id": algorithm_id, "archived": False}


@app.get("/algorithms/{algorithm_id}/export")
def export_algorithm(algorithm_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_algorithm(r, algorithm_id)
    if not cur:
        err.api_error(404, err.E_ALGORITHM_NOT_FOUND, "algorithm_not_found", algorithm_id=algorithm_id)
    _assert_resource_access(cur, current_user, allow_system=False)
    archive_response = _resolve_algorithm_archive_response(r, cur)
    if archive_response is not None:
        return archive_response
    payload = {
        "algorithm_id": cur.get("algorithm_id"),
        "task": cur.get("task"),
        "name": cur.get("name"),
        "impl": cur.get("impl"),
        "version": cur.get("version"),
        "description": cur.get("description") or "",
        "dependency_text": cur.get("dependency_text") or "",
        "entry_text": cur.get("entry_text") or "",
        "archive_filename": cur.get("archive_filename") or "",
        "archive_sha256": cur.get("archive_sha256") or "",
        "source_submission_id": cur.get("source_submission_id"),
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
        headers=_attachment_headers(filename),
    )


@app.get("/algorithm-submissions", response_model=list[AlgorithmSubmissionOut])
def list_algorithm_submissions_for_current_user(current_user: dict = Depends(get_current_user)):
    r = make_redis()
    username = _username_of(current_user)
    items = [
        _algorithm_submission_to_out(r, _ensure_submission_owner_algorithm_synced(r, item))
        for item in _list_all_algorithm_submissions(r)
        if str(item.get("owner_id") or "") == username
    ]
    return items


@app.post("/algorithm-submissions", response_model=AlgorithmSubmissionOut)
def create_algorithm_submission(payload: AlgorithmSubmissionCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    owner_id = _username_of(current_user)
    task_label = _normalize_algorithm_task_label(payload.task_type, field="algorithm_submission.task_type")
    task_type = TASK_TYPE_BY_LABEL.get(task_label, "").strip().lower()
    name = _validate_text_encoding(payload.name or "", "algorithm_submission.name").strip()
    if not name:
        err.api_error(400, err.E_HTTP, "algorithm_submission_name_required")
    archive_filename = Path(str(payload.archive_filename or "").strip() or "").name
    if not archive_filename:
        err.api_error(400, err.E_HTTP, "algorithm_archive_filename_required")
    archive_bytes = _decode_algorithm_submission_archive(payload.archive_b64)
    submission_id = f"algsub_{uuid.uuid4().hex[:12]}"
    storage_path, archive_size, archive_sha256 = _store_algorithm_submission_archive(owner_id, submission_id, archive_filename, archive_bytes)
    created = time.time()
    data = {
        "submission_id": submission_id,
        "task_type": task_type,
        "name": name,
        "version": _validate_text_encoding(payload.version or "v1", "algorithm_submission.version") or "v1",
        "description": _validate_text_encoding(payload.description or "", "algorithm_submission.description"),
        "dependency_text": _validate_text_encoding(payload.dependency_text or "", "algorithm_submission.dependency_text"),
        "entry_text": _validate_text_encoding(payload.entry_text or "", "algorithm_submission.entry_text"),
        "archive_filename": archive_filename,
        "archive_size": archive_size,
        "archive_sha256": archive_sha256,
        "archive_path": storage_path,
        "owner_id": owner_id,
        "status": "pending",
        "review_note": "",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": created,
        "platform_algorithm_id": None,
    }
    save_algorithm_submission(r, submission_id, data)
    return _algorithm_submission_to_out(r, data)


@app.get("/algorithm-submissions/{submission_id}/download")
def download_algorithm_submission_archive(submission_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    username = _username_of(current_user)
    is_admin = _normalize_user_role(current_user) == "admin"
    if str(cur.get("owner_id") or "") != username and not is_admin:
        err.api_error(403, err.E_HTTP, "forbidden_access")
    archive_path = Path(str(cur.get("archive_path") or "")).resolve()
    if not archive_path.exists() or not archive_path.is_file():
        err.api_error(404, err.E_HTTP, "algorithm_archive_not_found", submission_id=submission_id)
    filename = str(cur.get("archive_filename") or archive_path.name).strip() or archive_path.name
    return StreamingResponse(
        open(archive_path, "rb"),
        media_type="application/octet-stream",
        headers=_attachment_headers(filename),
    )


@app.delete("/algorithm-submissions/{submission_id}")
def delete_algorithm_submission_for_current_user(submission_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    username = _username_of(current_user)
    is_admin = _normalize_user_role(current_user) == "admin"
    if str(cur.get("owner_id") or "") != username and not is_admin:
        err.api_error(403, err.E_HTTP, "forbidden_access")

    _delete_algorithm_submission_by_record(r, cur)
    return {"ok": True, "submission_id": submission_id}


@app.post("/algorithm-submissions/{submission_id}/publish-community", response_model=AlgorithmSubmissionOut)
def publish_algorithm_submission_to_community(
    submission_id: str,
    payload: AlgorithmSubmissionPublish,
    current_user: dict = Depends(get_current_user),
):
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    owner_id = _username_of(current_user)
    if str(cur.get("owner_id") or "") != owner_id:
        err.api_error(403, err.E_HTTP, "forbidden_access")
    if str(cur.get("status") or "").strip().lower() != "approved":
        err.api_error(409, err.E_HTTP, "algorithm_submission_not_approved", submission_id=submission_id)
    community_algorithm_id = _publish_algorithm_submission_to_community(
        r,
        cur,
        owner_id,
        payload.community_description,
    )
    cur["community_algorithm_id"] = community_algorithm_id
    cur["community_published_at"] = time.time()
    save_algorithm_submission(r, submission_id, cur)
    return _algorithm_submission_to_out(r, cur)


@app.post("/algorithm-submissions/{submission_id}/unpublish-community", response_model=AlgorithmSubmissionOut)
def unpublish_algorithm_submission_from_community(submission_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    owner_id = _username_of(current_user)
    if str(cur.get("owner_id") or "") != owner_id:
        err.api_error(403, err.E_HTTP, "forbidden_access")
    community_algorithm_id = str(cur.get("community_algorithm_id") or "").strip()
    if not community_algorithm_id:
        err.api_error(409, err.E_HTTP, "algorithm_submission_not_published", submission_id=submission_id)
    source_name = str(cur.get("algorithm_name") or community_algorithm_id).strip() or community_algorithm_id
    _remove_algorithm_download_copies(
        r,
        source_algorithm_id=community_algorithm_id,
        source_owner_id=owner_id,
        notice_title="社区算法已下架",
        notice_message=f"你下载的社区算法“{source_name}”已被发布者下架，副本已从你的算法库中移除。",
    )
    community_algorithm = load_algorithm(r, community_algorithm_id)
    if community_algorithm:
        if not _is_submission_community_algorithm(community_algorithm, submission_id, owner_id):
            err.api_error(409, err.E_HTTP, "algorithm_submission_community_mismatch", submission_id=submission_id)
        _delete_algorithm_record_with_related_state(r, community_algorithm)
    cur["community_algorithm_id"] = None
    cur["community_published_at"] = None
    save_algorithm_submission(r, submission_id, cur)
    return _algorithm_submission_to_out(r, cur)


@app.get("/admin/users", response_model=list[UserOut])
def admin_list_registered_users(
    limit: int = Query(2000, ge=1, le=10000),
    current_user: dict = Depends(get_current_user),
):
    """列出已注册用户的用户名等信息（管理员）。"""
    _require_admin(current_user)
    r = make_redis()
    items = list_users(r, limit=limit) or []
    out: list[UserOut] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        u = str(raw.get("username") or "").strip()
        if not u:
            continue
        out.append(
            UserOut(
                username=u,
                display_name=str(raw.get("display_name") or ""),
                role=str(raw.get("role") or "user"),
                created_at=float(raw.get("created_at") or 0),
            )
        )
    out.sort(key=lambda x: (str(x.username or "").lower(), str(x.username or "")))
    return out


@app.post("/admin/users/{username}/purge-algorithms")
def admin_purge_user_algorithms(username: str, current_user: dict = Depends(get_current_user)):
    """管理员：清理指定用户的用户算法、接入申请及关联运行记录（不含 system 内置）。"""
    _require_admin(current_user)
    target = str(username or "").strip()
    if not target or target == "system":
        err.api_error(400, err.E_HTTP, "invalid_username", username=target)
    if target == _ADMIN_USERNAME:
        err.api_error(403, err.E_HTTP, "admin_purge_forbidden", detail="reserved account")
    r = make_redis()
    counts = _purge_user_algorithm_library(r, target)
    return {"ok": True, "username": target, **counts}


@app.get("/admin/algorithm-submissions", response_model=list[AlgorithmSubmissionOut])
def admin_list_algorithm_submissions(
    status: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    r = make_redis()
    status_value = str(status or "").strip().lower()
    items = []
    for item in _list_all_algorithm_submissions(r):
        item_status = str(item.get("status") or "").strip().lower()
        if status_value and item_status != status_value:
            continue
        items.append(_algorithm_submission_to_out(r, _ensure_submission_owner_algorithm_synced(r, item)))
    return items


@app.post("/admin/algorithm-submissions/{submission_id}/review", response_model=AlgorithmSubmissionOut)
def admin_review_algorithm_submission(
    submission_id: str,
    payload: AlgorithmSubmissionReview,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    status = _normalize_algorithm_submission_status(payload.status)
    cur["status"] = status
    cur["review_note"] = _validate_text_encoding(payload.review_note or "", "algorithm_submission.review_note")
    cur["reviewed_by"] = _username_of(current_user)
    cur["reviewed_at"] = time.time()
    runtime_ready = status == "approved" and bool(payload.runtime_ready)
    cur["runtime_ready"] = runtime_ready
    owner_algorithm_id = str(cur.get("owner_algorithm_id") or "").strip()
    if status == "approved":
        cur["owner_algorithm_id"] = _upsert_algorithm_submission_owner_algorithm(r, cur, runtime_ready=runtime_ready)
    elif owner_algorithm_id:
        _set_platform_algorithm_runtime_state(r, owner_algorithm_id, False)
    platform_algorithm_id = str(cur.get("platform_algorithm_id") or "").strip()
    if platform_algorithm_id:
        _set_platform_algorithm_runtime_state(r, platform_algorithm_id, runtime_ready)
    save_algorithm_submission(r, submission_id, cur)
    owner_id = str(cur.get("owner_id") or "").strip()
    if owner_id:
        if status == "approved":
            extra = ""
            if cur.get("platform_algorithm_id"):
                extra = f" 已生成平台留档算法：{cur['platform_algorithm_id']}。"
            note = f"你提交的算法代码包“{cur.get('name') or submission_id}”已审核通过。{extra}"
            if cur.get("review_note"):
                note = f"{note} 审核说明：{cur['review_note']}"
            _create_notice(r, owner_id, "算法代码接入申请已通过", note, kind="success")
        else:
            note = f"你提交的算法代码包“{cur.get('name') or submission_id}”未通过审核。"
            if cur.get("review_note"):
                note = f"{note} 审核说明：{cur['review_note']}"
            _create_notice(r, owner_id, "算法代码接入申请未通过", note, kind="warning")
    return _algorithm_submission_to_out(r, cur)


@app.post("/admin/algorithm-submissions/{submission_id}/promote-platform", response_model=AlgorithmSubmissionOut)
def admin_promote_algorithm_submission_to_platform(
    submission_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    r = make_redis()
    cur = load_algorithm_submission(r, submission_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "algorithm_submission_not_found", submission_id=submission_id)
    if str(cur.get("status") or "").strip().lower() != "approved":
        err.api_error(409, err.E_HTTP, "algorithm_submission_not_approved", submission_id=submission_id)
    if not bool(cur.get("runtime_ready")):
        err.api_error(409, err.E_HTTP, "algorithm_submission_not_runtime_ready", submission_id=submission_id)

    cur["platform_algorithm_id"] = _promote_algorithm_submission_to_platform(r, cur, runtime_ready=True)
    cur["promoted_by"] = _username_of(current_user)
    cur["promoted_at"] = time.time()
    cur["owner_algorithm_id"] = None
    cur["community_algorithm_id"] = None
    save_algorithm_submission(r, submission_id, cur)
    _purge_submission_related_algorithms(r, cur, keep_algorithm_ids={str(cur.get("platform_algorithm_id") or "").strip()})

    owner_id = str(cur.get("owner_id") or "").strip()
    if owner_id:
        _create_notice(
            r,
            owner_id,
            "算法已被收录为平台算法",
            f"你提交的算法代码包“{cur.get('name') or submission_id}”已由管理员收录为平台算法：{cur['platform_algorithm_id']}。",
            kind="success",
        )
    return _algorithm_submission_to_out(r, cur)


@app.get("/metrics", response_model=list[MetricOut])
def get_metrics(
    limit: int = 500,
    scope: str = Query("manage", description="manage|mine|ready"),
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    r = make_redis()
    _ensure_catalog_defaults(r)
    _run_reconcile_job(r, "metrics", _reconcile_metric_records)
    username = _username_of(current_user)
    scope_value = str(scope or "manage").strip().lower()
    status_value = str(status or "").strip().lower()
    task_filter = str(task_type or "").strip().lower()
    items = _list_all_metric_records(r)
    out = []
    owner_name_cache: dict[str, str] = {}
    for item in items:
        owner_id = str(item.get("owner_id") or "system").strip() or "system"
        item_status = str(item.get("status") or "").strip().lower()
        item_task_types = _normalize_metric_task_types(item.get("task_types") if isinstance(item.get("task_types"), list) else [])
        if task_filter and item_task_types and task_filter not in item_task_types:
            continue
        if status_value and item_status != status_value:
            continue
        if scope_value == "ready":
            if item_status != "approved" or not bool(item.get("runtime_ready")):
                continue
        elif scope_value == "mine":
            if owner_id != username:
                continue
        elif scope_value == "community":
            if owner_id == "system":
                continue
            if str(item.get("visibility") or "private").strip().lower() != "public":
                continue
            if not bool(item.get("allow_download")):
                continue
        else:
            if owner_id != "system" and owner_id != username:
                continue
        out.append(MetricOut(**_with_owner_display_name(r, item, cache=owner_name_cache)))
    out.sort(key=lambda x: (x.owner_id != "system", x.status != "approved", x.display_name or x.name or x.metric_key))
    return out[:limit]


@app.post("/metrics", response_model=MetricOut)
def create_metric(payload: MetricCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    metric_id = f"metric_{uuid.uuid4().hex[:10]}"
    metric_key = _resolve_metric_key_for_create(r, payload.metric_key, payload.name)
    created = time.time()
    data = {
        "metric_id": metric_id,
        "metric_key": metric_key,
        "name": _validate_text_encoding(payload.name, "metric.name"),
        "display_name": _validate_text_encoding(payload.display_name or payload.name, "metric.display_name"),
        "description": _validate_text_encoding(payload.description or "", "metric.description"),
        "task_types": _normalize_metric_task_types(payload.task_types),
        "direction": _normalize_metric_direction(payload.direction),
        "requires_reference": bool(payload.requires_reference),
        "implementation_type": _normalize_metric_implementation_type(payload.implementation_type),
        "formula_text": _validate_text_encoding(payload.formula_text or "", "metric.formula_text"),
        "code_text": _validate_text_encoding(payload.code_text or "", "metric.code_text"),
        "code_filename": _validate_text_encoding(payload.code_filename or "", "metric.code_filename"),
        "owner_id": _username_of(current_user),
        "status": "pending",
        "runtime_ready": False,
        "review_note": "",
        "reviewed_by": None,
        "reviewed_at": None,
        "visibility": "private",
        "allow_download": False,
        "download_count": 0,
        "source_owner_id": None,
        "source_metric_id": None,
        "community_published_at": None,
        "created_at": created,
    }
    save_metric(r, metric_id, data)
    return MetricOut(**data)


@app.patch("/metrics/{metric_id}", response_model=MetricOut)
def patch_metric(metric_id: str, payload: MetricPatch, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_metric(r, metric_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    _assert_metric_manage_access(cur, current_user)
    was_public = str(cur.get("visibility") or "private").strip().lower() == "public"
    if payload.metric_key is not None:
        fallback_name = payload.display_name or payload.name or cur.get("display_name") or cur.get("name")
        cur["metric_key"] = _resolve_metric_key_for_patch(r, metric_id, payload.metric_key, fallback_name)
    if payload.name is not None:
        cur["name"] = _validate_text_encoding(payload.name, "metric.name")
    if payload.display_name is not None:
        cur["display_name"] = _validate_text_encoding(payload.display_name, "metric.display_name")
    if payload.description is not None:
        cur["description"] = _validate_text_encoding(payload.description, "metric.description")
    if payload.task_types is not None:
        cur["task_types"] = _normalize_metric_task_types(payload.task_types)
    if payload.direction is not None:
        cur["direction"] = _normalize_metric_direction(payload.direction)
    if payload.requires_reference is not None:
        cur["requires_reference"] = bool(payload.requires_reference)
    if payload.implementation_type is not None:
        cur["implementation_type"] = _normalize_metric_implementation_type(payload.implementation_type)
    if payload.formula_text is not None:
        cur["formula_text"] = _validate_text_encoding(payload.formula_text, "metric.formula_text")
    if payload.code_text is not None:
        cur["code_text"] = _validate_text_encoding(payload.code_text, "metric.code_text")
    if payload.code_filename is not None:
        cur["code_filename"] = _validate_text_encoding(payload.code_filename, "metric.code_filename")
    if str(cur.get("owner_id") or "") != "system":
        cur["status"] = "pending"
        cur["runtime_ready"] = False
        cur["review_note"] = ""
        cur["reviewed_by"] = None
        cur["reviewed_at"] = None
        cur["visibility"] = "private"
        cur["allow_download"] = False
        cur["community_published_at"] = None
    save_metric(r, metric_id, cur)
    if (
        was_public
        and str(cur.get("visibility") or "private").strip().lower() != "public"
        and str(cur.get("owner_id") or "").strip() != "system"
        and not str(cur.get("source_metric_id") or "").strip()
    ):
        source_name = str(cur.get("display_name") or cur.get("name") or metric_id).strip() or metric_id
        _remove_metric_download_copies(
            r,
            source_metric_id=metric_id,
            source_owner_id=str(cur.get("owner_id") or "").strip(),
            notice_title="社区指标已下架",
            notice_message=f"你下载的社区指标“{source_name}”已被发布者下架，副本已从你的指标库中移除。",
        )
    return MetricOut(**cur)


@app.delete("/metrics/{metric_id}")
def remove_metric(metric_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_metric(r, metric_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    _assert_metric_manage_access(cur, current_user)
    owner_id = str(cur.get("owner_id") or "").strip()
    if owner_id and owner_id != "system" and not str(cur.get("source_metric_id") or "").strip():
        source_name = str(cur.get("display_name") or cur.get("name") or metric_id).strip() or metric_id
        _remove_metric_download_copies(
            r,
            source_metric_id=metric_id,
            source_owner_id=owner_id,
            notice_title="社区指标已删除",
            notice_message=f"你下载的社区指标“{source_name}”已被发布者删除，副本已从你的指标库中移除。",
        )
    delete_metric(r, metric_id)
    return {"ok": True, "metric_id": metric_id}


@app.post("/metrics/{metric_id}/publish-community", response_model=MetricOut)
def publish_metric_to_community(
    metric_id: str,
    payload: MetricPublish | None = Body(None),
    current_user: dict = Depends(get_current_user),
):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_metric(r, metric_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    owner_id = _username_of(current_user)
    if str(cur.get("owner_id") or "") != owner_id:
        err.api_error(403, err.E_HTTP, "forbidden_access")
    if str(cur.get("status") or "").strip().lower() != "approved":
        err.api_error(409, err.E_HTTP, "metric_not_approved", metric_id=metric_id)
    implementation_type = str(cur.get("implementation_type") or "").strip().lower()
    if implementation_type == "python" and not bool(cur.get("runtime_ready")):
        err.api_error(409, err.E_HTTP, "metric_not_runtime_ready", metric_id=metric_id)
    community_description = _validate_text_encoding(
        (payload.community_description if payload else "") or "",
        "metric.community_description",
    ).strip()
    if community_description:
        cur["description"] = community_description
    cur["visibility"] = "public"
    cur["allow_download"] = True
    cur["community_published_at"] = cur.get("community_published_at") or time.time()
    cur["download_count"] = int(cur.get("download_count") or 0)
    save_metric(r, metric_id, cur)
    return MetricOut(**cur)


@app.post("/metrics/{metric_id}/unpublish-community", response_model=MetricOut)
def unpublish_metric_from_community(metric_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_metric(r, metric_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    owner_id = _username_of(current_user)
    if str(cur.get("owner_id") or "") != owner_id:
        err.api_error(403, err.E_HTTP, "forbidden_access")
    if str(cur.get("source_metric_id") or "").strip():
        err.api_error(409, err.E_HTTP, "metric_community_copy_readonly", metric_id=metric_id)
    if str(cur.get("visibility") or "private").strip().lower() != "public":
        err.api_error(409, err.E_HTTP, "metric_not_published", metric_id=metric_id)
    cur["visibility"] = "private"
    cur["allow_download"] = False
    cur["community_published_at"] = None
    save_metric(r, metric_id, cur)
    source_name = str(cur.get("display_name") or cur.get("name") or metric_id).strip() or metric_id
    _remove_metric_download_copies(
        r,
        source_metric_id=metric_id,
        source_owner_id=owner_id,
        notice_title="社区指标已下架",
        notice_message=f"你下载的社区指标“{source_name}”已被发布者下架，副本已从你的指标库中移除。",
    )
    return MetricOut(**cur)


@app.post("/community/metrics/{metric_id}/download", response_model=MetricOut)
def download_metric_to_user_library(metric_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _ensure_catalog_defaults(r)
    source = load_metric(r, metric_id)
    if not source:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    source_owner = str(source.get("owner_id") or "system").strip() or "system"
    visibility = str(source.get("visibility") or "private").strip().lower()
    if source_owner == "system" or visibility != "public" or not bool(source.get("allow_download")):
        err.api_error(403, err.E_HTTP, "metric_not_public", metric_id=metric_id)
    if str(source.get("status") or "").strip().lower() != "approved":
        err.api_error(409, err.E_HTTP, "metric_not_approved", metric_id=metric_id)

    target_owner = _username_of(current_user)
    if source_owner == target_owner:
        err.api_error(409, err.E_HTTP, "metric_already_owned", metric_id=metric_id)
    for existing in list_metrics(r, limit=5000) or []:
        if str(existing.get("owner_id") or "") != target_owner:
            continue
        if (
            str(existing.get("source_metric_id") or "") == metric_id
            and str(existing.get("source_owner_id") or "") == source_owner
        ):
            err.api_error(409, err.E_HTTP, "metric_already_downloaded", metric_id=metric_id)

    target_metric_id = f"metric_{uuid.uuid4().hex[:10]}"
    copied = dict(source)
    copied["metric_id"] = target_metric_id
    copied["metric_key"] = _make_unique_metric_copy_key(r, str(source.get("metric_key") or ""), target_owner)
    copied["owner_id"] = target_owner
    copied["created_at"] = time.time()
    copied["visibility"] = "private"
    copied["allow_download"] = False
    copied["download_count"] = 0
    copied["source_metric_id"] = metric_id
    copied["source_owner_id"] = source_owner
    copied["community_published_at"] = None
    source["download_count"] = int(source.get("download_count") or 0) + 1
    save_metric(r, metric_id, source)
    save_metric(r, target_metric_id, copied)
    return MetricOut(**copied)


@app.get("/admin/metrics", response_model=list[MetricOut])
def admin_list_metrics(
    status: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    if _normalize_user_role(current_user) != "admin":
        err.api_error(403, err.E_HTTP, "forbidden_access")
    r = make_redis()
    _ensure_catalog_defaults(r)
    status_value = str(status or "").strip().lower()
    out = []
    for item in _list_all_metric_records(r):
        if status_value and str(item.get("status") or "").lower() != status_value:
            continue
        out.append(MetricOut(**item))
    out.sort(key=lambda x: (x.status, -(x.created_at or 0)))
    return out


@app.post("/admin/metrics/{metric_id}/review", response_model=MetricOut)
def admin_review_metric(metric_id: str, payload: MetricReview, current_user: dict = Depends(get_current_user)):
    if _normalize_user_role(current_user) != "admin":
        err.api_error(403, err.E_HTTP, "forbidden_access")
    r = make_redis()
    _ensure_catalog_defaults(r)
    cur = load_metric(r, metric_id)
    if not cur:
        err.api_error(404, err.E_HTTP, "metric_not_found", metric_id=metric_id)
    cur["status"] = _normalize_metric_status(payload.status)
    cur["review_note"] = _validate_text_encoding(payload.review_note or "", "metric.review_note")
    implementation_type = str(cur.get("implementation_type") or "").lower()
    runtime_ready = bool(payload.runtime_ready) and cur["status"] == "approved"
    if runtime_ready and implementation_type == "python":
        try:
            validate_python_metric_code(cur.get("code_text") or "")
        except Exception as exc:
            err.api_error(400, err.E_HTTP, "metric_code_invalid", detail=str(exc))
    cur["runtime_ready"] = runtime_ready and implementation_type in {"builtin", "python"}
    cur["reviewed_by"] = _username_of(current_user)
    cur["reviewed_at"] = time.time()
    save_metric(r, metric_id, cur)
    return MetricOut(**cur)


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
    target_name = _make_owner_unique_algorithm_name(r, target_owner, str(source.get("name") or "涓嬭浇绠楁硶"))

    copied = dict(source)
    copied["algorithm_id"] = target_algorithm_id
    copied["owner_id"] = target_owner
    copied["name"] = target_name
    copied["created_at"] = time.time()
    copied["visibility"] = "private"
    copied["allow_use"] = True
    copied["allow_download"] = False
    copied["is_active"] = True
    source["download_count"] = int(source.get("download_count") or 0) + 1
    save_algorithm(r, algorithm_id, source)
    copied["source_algorithm_id"] = algorithm_id
    copied["source_owner_id"] = source_owner
    if str(copied.get("impl") or "").strip().lower() == "userpackage":
        copied["package_role"] = "downloaded_community"
        copied["runtime_ready"] = _is_userpackage_download_runtime_ready(copied)
    else:
        copied["runtime_ready"] = bool(source.get("runtime_ready"))
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
    _reconcile_algorithm_records(r)
    items = list_algorithms(r, limit=5000, owner_id=None, include_public=True) or []
    out = []
    for item in items:
      owner_id = str(item.get("owner_id") or "system")
      visibility = str(item.get("visibility") or "private").lower()
      if owner_id == "system":
          continue
      item = _normalize_algorithm_runtime_state(item)
      item_id = str(item.get("algorithm_id") or "").strip()
      if item_id:
          save_algorithm(r, item_id, item)
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
    _reconcile_dataset_records(r)
    items = list_datasets(r, limit=5000, owner_id=None, include_public=True) or []
    out = []
    for item in items:
      owner_id = str(item.get("owner_id") or "system")
      if owner_id == "system":
          continue
      if not _dataset_is_publicly_available(item):
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
                source_submission_id = str(source.get("source_submission_id") or "").strip()
                if source_submission_id:
                    submission = load_algorithm_submission(r, source_submission_id)
                    if submission:
                        submission["platform_algorithm_id"] = str(existing.get("algorithm_id") or "")
                        submission["owner_algorithm_id"] = None
                        submission["community_algorithm_id"] = None
                        save_algorithm_submission(r, source_submission_id, submission)
                        _purge_submission_related_algorithms(r, submission, keep_algorithm_ids={str(existing.get("algorithm_id") or "")})
                else:
                    _remove_algorithm_download_copies(
                        r,
                        source_algorithm_id=algorithm_id,
                        source_owner_id=source_owner,
                    )
                    _delete_algorithm_record_with_related_state(r, source)
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
            restored["runtime_ready"] = True
            restored["updated_at"] = time.time()
            restored["package_role"] = "platform"
            save_algorithm(r, str(existing.get("algorithm_id") or ""), restored)
            source_submission_id = str(source.get("source_submission_id") or "").strip()
            if source_submission_id:
                submission = load_algorithm_submission(r, source_submission_id)
                if submission:
                    submission["platform_algorithm_id"] = str(existing.get("algorithm_id") or "")
                    submission["owner_algorithm_id"] = None
                    submission["community_algorithm_id"] = None
                    save_algorithm_submission(r, source_submission_id, submission)
                    _purge_submission_related_algorithms(r, submission, keep_algorithm_ids={str(existing.get("algorithm_id") or "")})
            else:
                _remove_algorithm_download_copies(
                    r,
                    source_algorithm_id=algorithm_id,
                    source_owner_id=source_owner,
                )
                _delete_algorithm_record_with_related_state(r, source)
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
    promoted["runtime_ready"] = True
    promoted["source_algorithm_id"] = algorithm_id
    promoted["source_owner_id"] = source_owner
    promoted["package_role"] = "platform"
    save_algorithm(r, promoted["algorithm_id"], promoted)
    source_submission_id = str(source.get("source_submission_id") or "").strip()
    if source_submission_id:
        submission = load_algorithm_submission(r, source_submission_id)
        if submission:
            submission["platform_algorithm_id"] = promoted["algorithm_id"]
            submission["owner_algorithm_id"] = None
            submission["community_algorithm_id"] = None
            save_algorithm_submission(r, source_submission_id, submission)
            _purge_submission_related_algorithms(r, submission, keep_algorithm_ids={str(promoted["algorithm_id"])})
    else:
        _remove_algorithm_download_copies(
            r,
            source_algorithm_id=algorithm_id,
            source_owner_id=source_owner,
        )
        _delete_algorithm_record_with_related_state(r, source)

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
    _remove_dataset_download_copies(
        r,
        source_dataset_id=dataset_id,
        source_owner_id=source_owner,
        notice_title="社区数据集已下架",
        notice_message=f"你下载的社区数据集“{source_name}”已被管理员下架，副本已从你的数据集库中移除。",
    )
    if source_owner:
        _create_notice(
            r,
            source_owner,
            "社区数据集已被管理员下架",
            f"你上传的社区数据集“{source_name}”已被管理员下架。如需恢复，请修改后重新发布。",
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
    normalized_algorithm_ids = [
        str(x or "").strip() for x in (payload.algorithm_ids or []) if str(x or "").strip()
    ]
    algorithm_id = str(payload.algorithm_id or "").strip()
    if not normalized_algorithm_ids and algorithm_id:
        normalized_algorithm_ids = [algorithm_id]
    if not algorithm_id and normalized_algorithm_ids:
        algorithm_id = normalized_algorithm_ids[0]
    data = {
        "preset_id": preset_id,
        "name": _validate_text_encoding(payload.name, "preset.name"),
        "task_type": payload.task_type,
        "dataset_id": payload.dataset_id,
        "algorithm_id": algorithm_id,
        "algorithm_ids": normalized_algorithm_ids,
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
    if payload.algorithm_ids is not None:
        cur["algorithm_ids"] = [
            str(x or "").strip() for x in (payload.algorithm_ids or []) if str(x or "").strip()
        ]
        if not str(cur.get("algorithm_id") or "").strip() and cur["algorithm_ids"]:
            cur["algorithm_id"] = cur["algorithm_ids"][0]
    if payload.algorithm_id is not None and payload.algorithm_ids is None:
        aid = str(payload.algorithm_id or "").strip()
        cur["algorithm_ids"] = [aid] if aid else []
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


@app.post("/runs", response_model=RunOut)
def create_run(payload: RunCreate, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    _run_reconcile_job(r, "algorithms", _reconcile_algorithm_records, force=True)
    _run_reconcile_job(r, "datasets", _reconcile_dataset_records, force=True)
    _run_reconcile_job(r, "metrics", _reconcile_metric_records, force=True)
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
    alg = _normalize_algorithm_runtime_state(alg)
    _assert_resource_access(alg, current_user, allow_system=True)

    requested_params = dict(payload.params or {})
    requested_params["eval_mode"] = _normalize_eval_mode(getattr(payload, "eval_mode", None) or requested_params.get("eval_mode"))
    requested_metrics_raw = requested_params.get("metrics")
    runnable_metric_keys = {str(item.get("metric_key") or "").upper() for item in _list_runnable_metrics(r, task_type)}
    if isinstance(requested_metrics_raw, list):
        normalized_metrics = []
        for item in requested_metrics_raw:
            metric_key = str(item or "").strip().upper()
            if not metric_key:
                continue
            if metric_key not in runnable_metric_keys:
                err.api_error(409, err.E_HTTP, "metric_not_runnable", metric_key=metric_key, task_type=task_type)
            if metric_key not in normalized_metrics:
                normalized_metrics.append(metric_key)
        requested_params["metrics"] = normalized_metrics

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
    if str(alg.get("impl") or "").strip().lower() == "userpackage":
        algorithm_owner_id = str(alg.get("owner_id") or "system").strip() or "system"
        package_role = _infer_user_package_role(alg)
        is_owner_package = algorithm_owner_id == owner_id
        if algorithm_owner_id not in {"system", owner_id}:
            err.api_error(403, err.E_HTTP, "forbidden_access")
        can_use_runtime = is_owner_package or bool(alg.get("allow_use"))
        if package_role == "downloaded_community" and algorithm_owner_id == owner_id:
            can_use_runtime = True
        if alg.get("is_active") is False or not bool(alg.get("runtime_ready")) or not can_use_runtime:
            err.api_error(
                409,
                err.E_ALGORITHM_RUNTIME,
                "algorithm_package_not_runtime_ready",
                algorithm_id=algorithm_id,
                runtime_ready=bool(alg.get("runtime_ready")),
                is_active=alg.get("is_active", True),
                allow_use=bool(alg.get("allow_use")),
                owner_package=is_owner_package,
                package_role=package_role,
            )

    from .vision.dataset_access import count_paired_images, count_paired_videos

    data_root = Path(__file__).resolve().parents[1] / "data"
    # 纭繚鏁版嵁鐩綍瀛樺湪
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
        "params": requested_params,
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
    _cleanup_invalid_runs_for_owner(r, owner_id)
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
    _cleanup_invalid_runs_for_owner(r, owner_id)
    runs = list_runs(r, limit=limit, owner_id=owner_id)

    # ===== 绛涢€夊綋鍓嶅鍑鸿寖鍥?=====
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

    # ===== 灞曞钩 params / samples 瀛楁 =====
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
            headers=_attachment_headers(filename),
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
        headers=_attachment_headers(filename),
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
    username = current_user["username"]

    deleted = 0
    for data in list_runs(r, limit=5000, owner_id=username):
        if str(data.get("owner_id") or "") != username:
            continue

        if status and status != "all":
            if data.get("status") != status:
                continue

        delete_run(r, str(data.get("run_id") or ""))
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
        delete_run(r, run_id)
        deleted += 1

    return {"ok": True, "deleted": deleted, "skipped": skipped}



@app.get("/runs/{run_id}")
def get_run(run_id: str, current_user: dict = Depends(get_current_user)):
    r = make_redis()
    run = load_run(r, run_id)
    if not run:
        err.api_error(404, err.E_RUN_NOT_FOUND, "run_not_found", run_id=run_id)
    _assert_resource_access(run, current_user, allow_system=True)
    owner_id = str(run.get("owner_id") or "").strip()
    if owner_id:
        _cleanup_invalid_runs_for_owner(r, owner_id)
        run = load_run(r, run_id)
        if not run:
            err.api_error(404, err.E_RUN_NOT_FOUND, "run_not_found", run_id=run_id)
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
