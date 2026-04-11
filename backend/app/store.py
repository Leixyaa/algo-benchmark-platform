from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
import redis

from . import sql_store


logger = logging.getLogger(__name__)


def make_redis() -> redis.Redis:
    return redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)


def _dump(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load_json(payload: str | None) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    data = json.loads(payload)
    return data if isinstance(data, dict) else None


def _redis_set(r: redis.Redis, key: str, data: Dict[str, Any]) -> None:
    r.set(key, _dump(data))


def _redis_load(r: redis.Redis, key: str) -> Optional[Dict[str, Any]]:
    return _load_json(r.get(key))


def _warn_sql_fallback(action: str, exc: Exception) -> None:
    logger.warning("SQL store %s failed; falling back to Redis: %s", action, exc)


def _should_fallback_to_redis() -> bool:
    return sql_store.allow_redis_fallback()


def run_key(run_id: str) -> str:
    return f"run:{run_id}"


def save_run(r: redis.Redis, run_id: str, data: Dict[str, Any]) -> None:
    r.set(run_key(run_id), json.dumps(data, ensure_ascii=False))


def load_run(r: redis.Redis, run_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(run_key(run_id))
    if not s:
        return None
    return json.loads(s)


def list_runs(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None) -> list[Dict[str, Any]]:
    keys = r.keys("run:*")
    runs = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "run_id" in data:
                oid = data.get("owner_id", "system")
                visibility = str(data.get("visibility", "private") or "private").lower()
                if owner_id:
                    if oid != "system" and oid != owner_id and visibility != "public":
                        continue
                else:
                    if oid != "system" and visibility != "public":
                        continue
                runs.append(data)
        except Exception:
            continue
    runs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return runs[:limit]


def dataset_key(dataset_id: str) -> str:
    return f"dataset:{dataset_id}"


def algorithm_key(algorithm_id: str) -> str:
    return f"algorithm:{algorithm_id}"


def save_dataset(r: redis.Redis, dataset_id: str, data: Dict[str, Any]) -> None:
    r.set(dataset_key(dataset_id), json.dumps(data, ensure_ascii=False))


def load_dataset(r: redis.Redis, dataset_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(dataset_key(dataset_id))
    if not s:
        return None
    return json.loads(s)


def delete_dataset(r: redis.Redis, dataset_id: str) -> None:
    r.delete(dataset_key(dataset_id))


def list_datasets(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None, include_public: bool = False) -> list[Dict[str, Any]]:
    keys = r.keys("dataset:*")
    items = []
    for k in keys:
        # 排除非元数据键
        if ":version:" in k or ":fs_hash:" in k or ":scan:" in k:
            continue
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "dataset_id" in data:
                oid = data.get("owner_id", "system")
                visibility = str(data.get("visibility", "private") or "private").lower()
                # 如果指定了 owner_id，则只显示自己的 + system 的
                if owner_id:
                    if oid != "system" and oid != owner_id and not (include_public and visibility == "public"):
                        continue
                else:
                    # 如果没指定（游客），只显示 system 的
                    if oid != "system" and not (include_public and visibility == "public"):
                        continue
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def save_algorithm(r: redis.Redis, algorithm_id: str, data: Dict[str, Any]) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.save_algorithm(algorithm_id, data)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_algorithm", exc)
    _redis_set(r, algorithm_key(algorithm_id), data)


def load_algorithm(r: redis.Redis, algorithm_id: str) -> Optional[Dict[str, Any]]:
    if sql_store.is_enabled():
        try:
            item = sql_store.load_algorithm(algorithm_id)
            if item is not None:
                return item
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("load_algorithm", exc)
        if not _should_fallback_to_redis():
            return None
    return _redis_load(r, algorithm_key(algorithm_id))


def delete_algorithm(r: redis.Redis, algorithm_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_algorithm(algorithm_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_algorithm", exc)
    r.delete(algorithm_key(algorithm_id))


def list_algorithms(r: redis.Redis, limit: int = 500, owner_id: Optional[str] = None, include_public: bool = False) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_algorithms(limit=limit, owner_id=owner_id, include_public=include_public)
            if not _should_fallback_to_redis():
                return sql_items
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_algorithms", exc)
    keys = r.keys("algorithm:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "algorithm_id" in data:
                oid = data.get("owner_id", "system")
                visibility = str(data.get("visibility", "private") or "private").lower()
                if owner_id:
                    if oid != "system" and oid != owner_id and not (include_public and visibility == "public"):
                        continue
                else:
                    if oid != "system" and not (include_public and visibility == "public"):
                        continue
                items.append(data)
        except Exception:
            continue
    if sql_items is not None:
        merged: dict[str, Dict[str, Any]] = {
            str(x.get("algorithm_id") or ""): x for x in items if isinstance(x, dict) and x.get("algorithm_id")
        }
        for item in sql_items:
            if isinstance(item, dict) and item.get("algorithm_id"):
                merged[str(item.get("algorithm_id"))] = item
        items = list(merged.values())
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def preset_key(preset_id: str) -> str:
    return f"preset:{preset_id}"


def save_preset(r: redis.Redis, preset_id: str, data: Dict[str, Any]) -> None:
    r.set(preset_key(preset_id), json.dumps(data, ensure_ascii=False))


def load_preset(r: redis.Redis, preset_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(preset_key(preset_id))
    if not s:
        return None
    return json.loads(s)


def delete_preset(r: redis.Redis, preset_id: str) -> None:
    r.delete(preset_key(preset_id))


def list_presets(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None) -> list[Dict[str, Any]]:
    keys = r.keys("preset:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "preset_id" in data:
                oid = data.get("owner_id", "system")
                if owner_id:
                    if oid != "system" and oid != owner_id:
                        continue
                else:
                    if oid != "system":
                        continue
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
    return items[:limit]


def metric_key(metric_id: str) -> str:
    return f"metric:{metric_id}"


def save_metric(r: redis.Redis, metric_id: str, data: Dict[str, Any]) -> None:
    r.set(metric_key(metric_id), json.dumps(data, ensure_ascii=False))


def load_metric(r: redis.Redis, metric_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(metric_key(metric_id))
    if not s:
        return None
    return json.loads(s)


def delete_metric(r: redis.Redis, metric_id: str) -> None:
    r.delete(metric_key(metric_id))


def list_metrics(r: redis.Redis, limit: int = 500) -> list[Dict[str, Any]]:
    keys = r.keys("metric:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "metric_id" in data:
                items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def algorithm_submission_key(submission_id: str) -> str:
    return f"algorithm_submission:{submission_id}"


def save_algorithm_submission(r: redis.Redis, submission_id: str, data: Dict[str, Any]) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.save_algorithm_submission(submission_id, data)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_algorithm_submission", exc)
    _redis_set(r, algorithm_submission_key(submission_id), data)


def load_algorithm_submission(r: redis.Redis, submission_id: str) -> Optional[Dict[str, Any]]:
    if sql_store.is_enabled():
        try:
            item = sql_store.load_algorithm_submission(submission_id)
            if item is not None:
                return item
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("load_algorithm_submission", exc)
        if not _should_fallback_to_redis():
            return None
    return _redis_load(r, algorithm_submission_key(submission_id))


def delete_algorithm_submission(r: redis.Redis, submission_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_algorithm_submission(submission_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_algorithm_submission", exc)
    r.delete(algorithm_submission_key(submission_id))


def list_algorithm_submissions(r: redis.Redis, limit: int = 5000) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_algorithm_submissions(limit=limit)
            if not _should_fallback_to_redis():
                return sql_items
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_algorithm_submissions", exc)
    keys = r.keys("algorithm_submission:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "submission_id" in data:
                items.append(data)
        except Exception:
            continue
    if sql_items is not None:
        merged: dict[str, Dict[str, Any]] = {
            str(x.get("submission_id") or ""): x for x in items if isinstance(x, dict) and x.get("submission_id")
        }
        for item in sql_items:
            if isinstance(item, dict) and item.get("submission_id"):
                merged[str(item.get("submission_id"))] = item
        items = list(merged.values())
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def user_key(username: str) -> str:
    return f"user:{username}"


def save_user(r: redis.Redis, username: str, data: Dict[str, Any]) -> None:
    r.set(user_key(username), json.dumps(data, ensure_ascii=False))


def load_user(r: redis.Redis, username: str) -> Optional[Dict[str, Any]]:
    s = r.get(user_key(username))
    if not s:
        return None
    return json.loads(s)


def list_users(r: redis.Redis, limit: int = 1000) -> list[Dict[str, Any]]:
    keys = r.keys("user:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "username" in data:
                items.append(data)
        except Exception:
            continue
    return items[:limit]
