from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import sql_store  # noqa: E402
from app.store import make_redis  # noqa: E402


def _load_redis_dict(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class MigrationSpec:
    name: str
    pattern: str
    required_field: str
    save: Callable[[str, dict[str, Any]], None]
    skip_if_key_contains: tuple[str, ...] = ()


def _iter_items(pattern: str, required_field: str, skip_if_key_contains: tuple[str, ...] = ()) -> Iterable[tuple[str, dict[str, Any]]]:
    r = make_redis()
    for key in r.scan_iter(match=pattern):
        if any(part in key for part in skip_if_key_contains):
            continue
        item = _load_redis_dict(r.get(key))
        if not item or required_field not in item:
            continue
        yield str(item.get(required_field) or key.split(":", 1)[-1]), item


def _save_record(record_type: str) -> Callable[[str, dict[str, Any]], None]:
    def _inner(record_id: str, item: dict[str, Any]) -> None:
        sql_store.save_record(record_type, record_id, item)

    return _inner


def _save_comment_record(_: str, item: dict[str, Any]) -> None:
    record_id = ":".join(
        [
            str(item.get("resource_type") or ""),
            str(item.get("resource_id") or ""),
            str(item.get("comment_id") or ""),
        ]
    )
    sql_store.save_record("comment", record_id, item)


def _save_notice_record(_: str, item: dict[str, Any]) -> None:
    record_id = ":".join([str(item.get("username") or ""), str(item.get("notice_id") or "")])
    sql_store.save_record("notice", record_id, item)


def _migration_specs() -> list[MigrationSpec]:
    return [
        MigrationSpec("runs", "run:*", "run_id", _save_record("run")),
        MigrationSpec(
            "datasets",
            "dataset:*",
            "dataset_id",
            _save_record("dataset"),
            skip_if_key_contains=(":version:", ":fs_hash:", ":scan:"),
        ),
        MigrationSpec("algorithms", "algorithm:*", "algorithm_id", sql_store.save_algorithm),
        MigrationSpec("presets", "preset:*", "preset_id", _save_record("preset")),
        MigrationSpec("metrics", "metric:*", "metric_id", _save_record("metric")),
        MigrationSpec("algorithm_submissions", "algorithm_submission:*", "submission_id", sql_store.save_algorithm_submission),
        MigrationSpec("users", "user:*", "username", _save_record("user")),
        MigrationSpec("comments", "comment:*:*:*", "comment_id", _save_comment_record),
        MigrationSpec("notices", "notice:*:*", "notice_id", _save_notice_record),
        MigrationSpec("reports", "report:*", "report_id", _save_record("report")),
    ]


def migrate_spec(spec: MigrationSpec, dry_run: bool = False) -> tuple[int, int]:
    migrated = 0
    skipped = 0
    for item_id, item in _iter_items(spec.pattern, spec.required_field, spec.skip_if_key_contains):
        if dry_run:
            migrated += 1
            continue
        try:
            spec.save(item_id, item)
            migrated += 1
        except Exception:
            skipped += 1
            raise
    return migrated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate persistent resources from Redis to SQL store.")
    parser.add_argument("--dry-run", action="store_true", help="Only count Redis records; do not write SQL.")
    args = parser.parse_args()

    if not sql_store.is_enabled():
        print(f"SQL store is not configured. Set {sql_store.SQL_STORE_URL_ENV} or {sql_store.MYSQL_STORE_URL_ENV}.")
        return 2

    if not args.dry_run:
        sql_store.init_schema()

    mode = "dry-run" if args.dry_run else "migrated"
    counts: list[str] = []
    skipped_counts: list[str] = []
    for spec in _migration_specs():
        migrated, skipped = migrate_spec(spec, dry_run=args.dry_run)
        counts.append(f"{spec.name}={migrated}")
        skipped_counts.append(f"skipped_{spec.name}={skipped}")
    print(f"{mode}: {', '.join(counts)}, {', '.join(skipped_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
