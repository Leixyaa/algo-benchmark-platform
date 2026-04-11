from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


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


def _iter_items(pattern: str, required_field: str) -> Iterable[tuple[str, dict[str, Any]]]:
    r = make_redis()
    for key in r.scan_iter(match=pattern):
        item = _load_redis_dict(r.get(key))
        if not item or required_field not in item:
            continue
        yield str(item.get(required_field) or key.split(":", 1)[-1]), item


def migrate_algorithms(dry_run: bool = False) -> tuple[int, int]:
    migrated = 0
    skipped = 0
    for algorithm_id, item in _iter_items("algorithm:*", "algorithm_id"):
        if dry_run:
            migrated += 1
            continue
        try:
            sql_store.save_algorithm(algorithm_id, item)
            migrated += 1
        except Exception:
            skipped += 1
            raise
    return migrated, skipped


def migrate_submissions(dry_run: bool = False) -> tuple[int, int]:
    migrated = 0
    skipped = 0
    for submission_id, item in _iter_items("algorithm_submission:*", "submission_id"):
        if dry_run:
            migrated += 1
            continue
        try:
            sql_store.save_algorithm_submission(submission_id, item)
            migrated += 1
        except Exception:
            skipped += 1
            raise
    return migrated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate algorithm resources from Redis to SQL store.")
    parser.add_argument("--dry-run", action="store_true", help="Only count Redis records; do not write SQL.")
    args = parser.parse_args()

    if not sql_store.is_enabled():
        print(f"SQL store is not configured. Set {sql_store.SQL_STORE_URL_ENV} or {sql_store.MYSQL_STORE_URL_ENV}.")
        return 2

    if not args.dry_run:
        sql_store.init_schema()

    alg_count, alg_skipped = migrate_algorithms(dry_run=args.dry_run)
    sub_count, sub_skipped = migrate_submissions(dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "migrated"
    print(
        f"{mode}: algorithms={alg_count}, algorithm_submissions={sub_count}, "
        f"skipped_algorithms={alg_skipped}, skipped_submissions={sub_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
