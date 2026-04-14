from __future__ import annotations

import json
import logging
import time
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


def _merge_records(redis_items: list[Dict[str, Any]], sql_items: list[Dict[str, Any]] | None, id_field: str) -> list[Dict[str, Any]]:
    if sql_items is None:
        return redis_items
    merged: dict[str, Dict[str, Any]] = {
        str(x.get(id_field) or ""): x for x in redis_items if isinstance(x, dict) and x.get(id_field)
    }
    for item in sql_items:
        if not isinstance(item, dict):
            continue
        rid = str(item.get(id_field) or "")
        if not rid:
            continue
        if rid in merged and id_field == "run_id":
            merged[rid] = _pick_better_run(merged[rid], item)
        else:
            merged[rid] = item
    return list(merged.values())


def _recency_ts(item: Dict[str, Any]) -> float:
    try:
        return float(item.get("updated_at") or item.get("created_at") or 0)
    except Exception:
        return 0.0


def _pick_newer_record(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return b if _recency_ts(b) >= _recency_ts(a) else a


def _merge_records_prefer_newer(
    redis_items: list[Dict[str, Any]],
    sql_items: list[Dict[str, Any]] | None,
    id_field: str,
) -> list[Dict[str, Any]]:
    """SQL 与 Redis 双写时，按 updated_at/created_at 取较新，避免列表里出现已下架但仍为旧的 SQL 快照。"""
    if sql_items is None:
        return redis_items
    merged: dict[str, Dict[str, Any]] = {}
    for x in redis_items:
        if isinstance(x, dict) and x.get(id_field):
            merged[str(x.get(id_field))] = x
    for item in sql_items:
        if not isinstance(item, dict):
            continue
        rid = str(item.get(id_field) or "")
        if not rid:
            continue
        if rid not in merged:
            merged[rid] = item
        else:
            merged[rid] = _pick_newer_record(merged[rid], item)
    return list(merged.values())


def _bump_updated_at(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    out["updated_at"] = time.time()
    return out


def run_key(run_id: str) -> str:
    return f"run:{run_id}"


# SQL 写入失败（如 payload 超过 MySQL TEXT 上限）时会回退到 Redis；列表合并时不能再用 SQL 覆盖较新的 Redis。
_RUN_TERMINAL = frozenset({"done", "failed", "canceled"})


def _run_recency_tuple(item: Dict[str, Any]) -> tuple:
    st = str(item.get("status") or "").lower()
    if st in _RUN_TERMINAL:
        tier = 3
    elif st in ("running", "canceling"):
        tier = 2
    elif st in ("queued",):
        tier = 1
    else:
        tier = 0
    fin = float(item.get("finished_at") or 0)
    sta = float(item.get("started_at") or 0)
    crt = float(item.get("created_at") or 0)
    return (tier, fin, sta, crt)


def _pick_better_run(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    if not a:
        return b
    if not b:
        return a
    return a if _run_recency_tuple(a) >= _run_recency_tuple(b) else b


def save_run(r: redis.Redis, run_id: str, data: Dict[str, Any]) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.save_record("run", run_id, data)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_run", exc)
    _redis_set(r, run_key(run_id), data)


def load_run(r: redis.Redis, run_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, run_key(run_id))
    sql_item: Optional[Dict[str, Any]] = None
    if sql_store.is_enabled():
        try:
            sql_item = sql_store.load_record("run", run_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("load_run", exc)
            sql_item = None
        if sql_item is not None and redis_item is not None:
            return _pick_better_run(sql_item, redis_item)
        if sql_item is not None:
            return sql_item
        if not _should_fallback_to_redis():
            return None
    return redis_item


def delete_run(r: redis.Redis, run_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_record("run", run_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_run", exc)
    r.delete(run_key(run_id))


def list_runs(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("run", limit=limit, owner_id=owner_id, include_public=True)
            if not _should_fallback_to_redis():
                sql_items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                return sql_items[:limit]
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_runs", exc)
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
    runs = _merge_records(runs, sql_items, "run_id")
    runs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return runs[:limit]


def list_all_runs(r: redis.Redis, limit: int = 5000) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("run", limit=limit, filter_by_owner=False)
            if not _should_fallback_to_redis():
                sql_items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                return sql_items[:limit]
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_all_runs", exc)
    keys = r.keys("run:*")
    runs = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "run_id" in data:
                runs.append(data)
        except Exception:
            continue
    runs = _merge_records(runs, sql_items, "run_id")
    runs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return runs[:limit]


def dataset_key(dataset_id: str) -> str:
    return f"dataset:{dataset_id}"


def algorithm_key(algorithm_id: str) -> str:
    return f"algorithm:{algorithm_id}"


def save_dataset(r: redis.Redis, dataset_id: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_record("dataset", dataset_id, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_dataset", exc)
    _redis_set(r, dataset_key(dataset_id), payload)


def load_dataset(r: redis.Redis, dataset_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, dataset_key(dataset_id))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_record("dataset", dataset_id)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_dataset", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


def delete_dataset(r: redis.Redis, dataset_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_record("dataset", dataset_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_dataset", exc)
    r.delete(dataset_key(dataset_id))


def list_datasets(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None, include_public: bool = False) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("dataset", limit=limit, owner_id=owner_id, include_public=include_public)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_datasets", exc)
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
    items = _merge_records_prefer_newer(items, sql_items, "dataset_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def list_all_datasets(r: redis.Redis, limit: int = 5000) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("dataset", limit=limit, filter_by_owner=False)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_all_datasets", exc)
    keys = r.keys("dataset:*")
    items = []
    for k in keys:
        if ":version:" in k or ":fs_hash:" in k or ":scan:" in k:
            continue
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "dataset_id" in data:
                items.append(data)
        except Exception:
            continue
    items = _merge_records_prefer_newer(items, sql_items, "dataset_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def save_algorithm(r: redis.Redis, algorithm_id: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_algorithm(algorithm_id, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_algorithm", exc)
    _redis_set(r, algorithm_key(algorithm_id), payload)


def load_algorithm(r: redis.Redis, algorithm_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, algorithm_key(algorithm_id))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_algorithm(algorithm_id)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_algorithm", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


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
    items = _merge_records_prefer_newer(items, sql_items, "algorithm_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def list_all_algorithms(r: redis.Redis, limit: int = 5000) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_all_algorithms(limit=limit)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_all_algorithms", exc)
    keys = r.keys("algorithm:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "algorithm_id" in data:
                items.append(data)
        except Exception:
            continue
    items = _merge_records_prefer_newer(items, sql_items, "algorithm_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def preset_key(preset_id: str) -> str:
    return f"preset:{preset_id}"


def save_preset(r: redis.Redis, preset_id: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_record("preset", preset_id, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_preset", exc)
    _redis_set(r, preset_key(preset_id), payload)


def load_preset(r: redis.Redis, preset_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, preset_key(preset_id))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_record("preset", preset_id)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_preset", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


def delete_preset(r: redis.Redis, preset_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_record("preset", preset_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_preset", exc)
    r.delete(preset_key(preset_id))


def list_presets(r: redis.Redis, limit: int = 200, owner_id: Optional[str] = None) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("preset", limit=limit, owner_id=owner_id, include_public=False)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_presets", exc)
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
    items = _merge_records_prefer_newer(items, sql_items, "preset_id")
    items.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
    return items[:limit]


def metric_key(metric_id: str) -> str:
    return f"metric:{metric_id}"


def save_metric(r: redis.Redis, metric_id: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_record("metric", metric_id, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_metric", exc)
    _redis_set(r, metric_key(metric_id), payload)


def load_metric(r: redis.Redis, metric_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, metric_key(metric_id))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_record("metric", metric_id)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_metric", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


def delete_metric(r: redis.Redis, metric_id: str) -> None:
    if sql_store.is_enabled():
        try:
            sql_store.delete_record("metric", metric_id)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("delete_metric", exc)
    r.delete(metric_key(metric_id))


def list_metrics(r: redis.Redis, limit: int = 500) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("metric", limit=limit, filter_by_owner=False)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_metrics", exc)
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
    items = _merge_records_prefer_newer(items, sql_items, "metric_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def algorithm_submission_key(submission_id: str) -> str:
    return f"algorithm_submission:{submission_id}"


def save_algorithm_submission(r: redis.Redis, submission_id: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_algorithm_submission(submission_id, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_algorithm_submission", exc)
    _redis_set(r, algorithm_submission_key(submission_id), payload)


def load_algorithm_submission(r: redis.Redis, submission_id: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, algorithm_submission_key(submission_id))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_algorithm_submission(submission_id)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_algorithm_submission", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


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
    items = _merge_records_prefer_newer(items, sql_items, "submission_id")
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def user_key(username: str) -> str:
    return f"user:{username}"


def save_user(r: redis.Redis, username: str, data: Dict[str, Any]) -> None:
    payload = _bump_updated_at(data)
    if sql_store.is_enabled():
        try:
            sql_store.save_record("user", username, payload)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("save_user", exc)
    _redis_set(r, user_key(username), payload)


def load_user(r: redis.Redis, username: str) -> Optional[Dict[str, Any]]:
    redis_item = _redis_load(r, user_key(username))
    if not sql_store.is_enabled():
        return redis_item
    sql_item = None
    try:
        sql_item = sql_store.load_record("user", username)
    except Exception as exc:
        if not _should_fallback_to_redis():
            raise
        _warn_sql_fallback("load_user", exc)
    if sql_item is None:
        return redis_item
    if redis_item is None:
        return sql_item
    return _pick_newer_record(sql_item, redis_item)


def list_users(r: redis.Redis, limit: int = 1000) -> list[Dict[str, Any]]:
    sql_items: list[Dict[str, Any]] | None = None
    if sql_store.is_enabled():
        try:
            sql_items = sql_store.list_records("user", limit=limit, filter_by_owner=False)
        except Exception as exc:
            if not _should_fallback_to_redis():
                raise
            _warn_sql_fallback("list_users", exc)
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
    items = _merge_records_prefer_newer(items, sql_items, "username")
    return items[:limit]
