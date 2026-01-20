from __future__ import annotations

import json
from typing import Any, Dict, Optional
import redis


def make_redis() -> redis.Redis:
    # 默认本机 Redis
    return redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)


def run_key(run_id: str) -> str:
    return f"run:{run_id}"


def save_run(r: redis.Redis, run_id: str, data: Dict[str, Any]) -> None:
    r.set(run_key(run_id), json.dumps(data, ensure_ascii=False))


def load_run(r: redis.Redis, run_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(run_key(run_id))
    if not s:
        return None
    return json.loads(s)


def list_runs(r: redis.Redis, limit: int = 200) -> list[Dict[str, Any]]:
    # 简单实现：扫描 key（毕业设计够用）
    keys = r.keys("run:*")
    # 按创建时间排序（desc）
    runs = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        runs.append(json.loads(s))
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


def list_datasets(r: redis.Redis, limit: int = 200) -> list[Dict[str, Any]]:
    keys = r.keys("dataset:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        items.append(json.loads(s))
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def save_algorithm(r: redis.Redis, algorithm_id: str, data: Dict[str, Any]) -> None:
    r.set(algorithm_key(algorithm_id), json.dumps(data, ensure_ascii=False))


def load_algorithm(r: redis.Redis, algorithm_id: str) -> Optional[Dict[str, Any]]:
    s = r.get(algorithm_key(algorithm_id))
    if not s:
        return None
    return json.loads(s)


def delete_algorithm(r: redis.Redis, algorithm_id: str) -> None:
    r.delete(algorithm_key(algorithm_id))


def list_algorithms(r: redis.Redis, limit: int = 500) -> list[Dict[str, Any]]:
    keys = r.keys("algorithm:*")
    items = []
    for k in keys:
        s = r.get(k)
        if not s:
            continue
        items.append(json.loads(s))
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]
