from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional


try:
    from sqlalchemy import (
        Boolean,
        Column,
        Float,
        MetaData,
        String,
        Table,
        Text,
        create_engine,
        delete,
        insert,
        select,
        update,
    )
    from sqlalchemy.engine import Engine
except Exception:  # pragma: no cover - optional dependency until SQL store is enabled
    Boolean = Column = Float = MetaData = String = Table = Text = None  # type: ignore
    create_engine = delete = insert = select = update = None  # type: ignore
    Engine = object  # type: ignore


SQL_STORE_URL_ENV = "ABP_SQL_STORE_URL"
MYSQL_STORE_URL_ENV = "ABP_MYSQL_URL"
SQL_FALLBACK_REDIS_ENV = "ABP_SQL_FALLBACK_REDIS"


def get_database_url() -> str:
    return (os.getenv(SQL_STORE_URL_ENV) or os.getenv(MYSQL_STORE_URL_ENV) or "").strip()


def is_enabled() -> bool:
    return bool(get_database_url())


def allow_redis_fallback() -> bool:
    raw = str(os.getenv(SQL_FALLBACK_REDIS_ENV, "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


metadata = MetaData() if MetaData else None


def _table(name: str, *columns: Any) -> Any:
    if metadata is None or Table is None:
        return None
    return Table(name, metadata, *columns)


if metadata is not None:
    algorithms_table = _table(
        "abp_algorithms",
        Column("algorithm_id", String(191), primary_key=True),
        Column("owner_id", String(191), index=True),
        Column("task", String(64), index=True),
        Column("name", String(255), index=True),
        Column("impl", String(64), index=True),
        Column("visibility", String(32), index=True),
        Column("package_role", String(64), index=True),
        Column("source_submission_id", String(191), index=True),
        Column("source_owner_id", String(191), index=True),
        Column("source_algorithm_id", String(191), index=True),
        Column("allow_use", Boolean),
        Column("allow_download", Boolean),
        Column("is_active", Boolean),
        Column("runtime_ready", Boolean),
        Column("created_at", Float, index=True),
        Column("updated_at", Float, index=True),
        Column("payload_json", Text, nullable=False),
    )

    algorithm_submissions_table = _table(
        "abp_algorithm_submissions",
        Column("submission_id", String(191), primary_key=True),
        Column("owner_id", String(191), index=True),
        Column("task_type", String(64), index=True),
        Column("name", String(255), index=True),
        Column("status", String(32), index=True),
        Column("runtime_ready", Boolean, index=True),
        Column("owner_algorithm_id", String(191), index=True),
        Column("community_algorithm_id", String(191), index=True),
        Column("platform_algorithm_id", String(191), index=True),
        Column("created_at", Float, index=True),
        Column("reviewed_at", Float, index=True),
        Column("payload_json", Text, nullable=False),
    )

    store_records_table = _table(
        "abp_store_records",
        Column("record_type", String(64), primary_key=True),
        Column("record_id", String(191), primary_key=True),
        Column("owner_id", String(191), index=True),
        Column("visibility", String(32), index=True),
        Column("created_at", Float, index=True),
        Column("updated_at", Float, index=True),
        Column("sort_at", Float, index=True),
        Column("payload_json", Text, nullable=False),
    )
else:
    algorithms_table = None
    algorithm_submissions_table = None
    store_records_table = None


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = get_database_url()
    if not url:
        raise RuntimeError(f"{SQL_STORE_URL_ENV} is not configured")
    if create_engine is None or metadata is None:
        raise RuntimeError("SQL store dependencies are not installed. Install SQLAlchemy and PyMySQL first.")
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)


def init_schema() -> None:
    if not is_enabled():
        return
    if metadata is None:
        raise RuntimeError("SQL store dependencies are not installed. Install SQLAlchemy and PyMySQL first.")
    metadata.create_all(get_engine())


def _dump(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _load(payload: str | None) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _bool_or_none(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _record_values(record_type: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(data or {})
    created_at = _float_or_zero(item.get("created_at"))
    updated_at = _float_or_zero(item.get("updated_at") if item.get("updated_at") is not None else created_at)
    return {
        "record_type": str(record_type),
        "record_id": str(record_id),
        "owner_id": str(item.get("owner_id") or item.get("username") or "system"),
        "visibility": str(item.get("visibility") or "private"),
        "created_at": created_at,
        "updated_at": updated_at,
        "sort_at": updated_at or created_at,
        "payload_json": _dump(item),
    }


def _algorithm_values(algorithm_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(data or {})
    item["algorithm_id"] = str(item.get("algorithm_id") or algorithm_id)
    return {
        "algorithm_id": str(item.get("algorithm_id") or algorithm_id),
        "owner_id": str(item.get("owner_id") or "system"),
        "task": str(item.get("task") or ""),
        "name": str(item.get("name") or ""),
        "impl": str(item.get("impl") or ""),
        "visibility": str(item.get("visibility") or "private"),
        "package_role": str(item.get("package_role") or ""),
        "source_submission_id": str(item.get("source_submission_id") or ""),
        "source_owner_id": str(item.get("source_owner_id") or ""),
        "source_algorithm_id": str(item.get("source_algorithm_id") or ""),
        "allow_use": _bool_or_none(item.get("allow_use")),
        "allow_download": _bool_or_none(item.get("allow_download")),
        "is_active": _bool_or_none(item.get("is_active")),
        "runtime_ready": _bool_or_none(item.get("runtime_ready")),
        "created_at": float(item.get("created_at") or 0),
        "updated_at": float(item.get("updated_at") or 0) if item.get("updated_at") is not None else None,
        "payload_json": _dump(item),
    }


def _submission_values(submission_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(data or {})
    item["submission_id"] = str(item.get("submission_id") or submission_id)
    return {
        "submission_id": str(item.get("submission_id") or submission_id),
        "owner_id": str(item.get("owner_id") or ""),
        "task_type": str(item.get("task_type") or ""),
        "name": str(item.get("name") or ""),
        "status": str(item.get("status") or ""),
        "runtime_ready": _bool_or_none(item.get("runtime_ready")),
        "owner_algorithm_id": str(item.get("owner_algorithm_id") or ""),
        "community_algorithm_id": str(item.get("community_algorithm_id") or ""),
        "platform_algorithm_id": str(item.get("platform_algorithm_id") or ""),
        "created_at": float(item.get("created_at") or 0),
        "reviewed_at": float(item.get("reviewed_at") or 0) if item.get("reviewed_at") is not None else None,
        "payload_json": _dump(item),
    }


def _upsert(table: Any, pk_name: str, pk_value: str, values: Dict[str, Any]) -> None:
    init_schema()
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(update(table).where(table.c[pk_name] == pk_value).values(**values))
        if int(result.rowcount or 0) == 0:
            conn.execute(insert(table).values(**values))


def save_algorithm(algorithm_id: str, data: Dict[str, Any]) -> None:
    values = _algorithm_values(algorithm_id, data)
    _upsert(algorithms_table, "algorithm_id", values["algorithm_id"], values)


def load_algorithm(algorithm_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    stmt = select(algorithms_table.c.payload_json).where(algorithms_table.c.algorithm_id == algorithm_id)
    with get_engine().connect() as conn:
        row = conn.execute(stmt).first()
    return _load(row[0]) if row else None


def delete_algorithm(algorithm_id: str) -> None:
    init_schema()
    with get_engine().begin() as conn:
        conn.execute(delete(algorithms_table).where(algorithms_table.c.algorithm_id == algorithm_id))


def list_algorithms(limit: int = 500, owner_id: Optional[str] = None, include_public: bool = False) -> list[Dict[str, Any]]:
    init_schema()
    stmt = select(algorithms_table.c.payload_json).order_by(algorithms_table.c.created_at.desc()).limit(int(limit or 500))
    if owner_id:
        visibility_filter = algorithms_table.c.visibility == "public"
        if include_public:
            stmt = stmt.where(
                (algorithms_table.c.owner_id == "system")
                | (algorithms_table.c.owner_id == owner_id)
                | visibility_filter
            )
        else:
            stmt = stmt.where((algorithms_table.c.owner_id == "system") | (algorithms_table.c.owner_id == owner_id))
    else:
        if include_public:
            stmt = stmt.where((algorithms_table.c.owner_id == "system") | (algorithms_table.c.visibility == "public"))
        else:
            stmt = stmt.where(algorithms_table.c.owner_id == "system")
    with get_engine().connect() as conn:
        rows = conn.execute(stmt).all()
    return [item for item in (_load(row[0]) for row in rows) if item]


def list_all_algorithms(limit: int = 5000) -> list[Dict[str, Any]]:
    init_schema()
    stmt = select(algorithms_table.c.payload_json).order_by(algorithms_table.c.created_at.desc()).limit(int(limit or 5000))
    with get_engine().connect() as conn:
        rows = conn.execute(stmt).all()
    return [item for item in (_load(row[0]) for row in rows) if item]


def save_algorithm_submission(submission_id: str, data: Dict[str, Any]) -> None:
    values = _submission_values(submission_id, data)
    _upsert(algorithm_submissions_table, "submission_id", values["submission_id"], values)


def load_algorithm_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    stmt = select(algorithm_submissions_table.c.payload_json).where(algorithm_submissions_table.c.submission_id == submission_id)
    with get_engine().connect() as conn:
        row = conn.execute(stmt).first()
    return _load(row[0]) if row else None


def delete_algorithm_submission(submission_id: str) -> None:
    init_schema()
    with get_engine().begin() as conn:
        conn.execute(delete(algorithm_submissions_table).where(algorithm_submissions_table.c.submission_id == submission_id))


def list_algorithm_submissions(limit: int = 5000) -> list[Dict[str, Any]]:
    init_schema()
    stmt = select(algorithm_submissions_table.c.payload_json).order_by(algorithm_submissions_table.c.created_at.desc()).limit(int(limit or 5000))
    with get_engine().connect() as conn:
        rows = conn.execute(stmt).all()
    return [item for item in (_load(row[0]) for row in rows) if item]


def save_record(record_type: str, record_id: str, data: Dict[str, Any]) -> None:
    values = _record_values(record_type, record_id, data)
    init_schema()
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            update(store_records_table)
            .where(
                (store_records_table.c.record_type == values["record_type"])
                & (store_records_table.c.record_id == values["record_id"])
            )
            .values(**values)
        )
        if int(result.rowcount or 0) == 0:
            conn.execute(insert(store_records_table).values(**values))


def load_record(record_type: str, record_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    stmt = select(store_records_table.c.payload_json).where(
        (store_records_table.c.record_type == str(record_type))
        & (store_records_table.c.record_id == str(record_id))
    )
    with get_engine().connect() as conn:
        row = conn.execute(stmt).first()
    return _load(row[0]) if row else None


def delete_record(record_type: str, record_id: str) -> None:
    init_schema()
    with get_engine().begin() as conn:
        conn.execute(
            delete(store_records_table).where(
                (store_records_table.c.record_type == str(record_type))
                & (store_records_table.c.record_id == str(record_id))
            )
        )


def list_records(
    record_type: str,
    limit: int = 500,
    owner_id: Optional[str] = None,
    include_public: bool = False,
    filter_by_owner: bool = True,
) -> list[Dict[str, Any]]:
    init_schema()
    stmt = (
        select(store_records_table.c.payload_json)
        .where(store_records_table.c.record_type == str(record_type))
        .order_by(store_records_table.c.sort_at.desc())
        .limit(int(limit or 500))
    )
    if filter_by_owner:
        if owner_id:
            if include_public:
                stmt = stmt.where(
                    (store_records_table.c.owner_id == "system")
                    | (store_records_table.c.owner_id == owner_id)
                    | (store_records_table.c.visibility == "public")
                )
            else:
                stmt = stmt.where((store_records_table.c.owner_id == "system") | (store_records_table.c.owner_id == owner_id))
        elif include_public:
            stmt = stmt.where((store_records_table.c.owner_id == "system") | (store_records_table.c.visibility == "public"))
        else:
            stmt = stmt.where(store_records_table.c.owner_id == "system")
    with get_engine().connect() as conn:
        rows = conn.execute(stmt).all()
    return [item for item in (_load(row[0]) for row in rows) if item]
