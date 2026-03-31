# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from pathlib import Path


def _iter_py_files(app_dir: Path) -> list[Path]:
    out: list[Path] = []
    for p in app_dir.rglob("*.py"):
        if p.name == "__pycache__":
            continue
        out.append(p)
    return sorted(out)


def _extract_e_literals(text: str) -> set[str]:
    return set(re.findall(r"['\"](E_[A-Z0-9_]+)['\"]", text))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    from backend.app import errors as err

    const_codes: list[str] = []
    for k, v in vars(err).items():
        if k.startswith("E_") and isinstance(v, str):
            const_codes.append(v)

    if len(const_codes) != len(set(const_codes)):
        dup = sorted([x for x in set(const_codes) if const_codes.count(x) > 1])
        raise RuntimeError(f"duplicate_error_code_values: {dup}")

    defs_codes = set(err.ERROR_DEFS.keys())
    const_codes_set = set(const_codes)

    miss_in_defs = sorted(const_codes_set - defs_codes)
    extra_in_defs = sorted(defs_codes - const_codes_set)
    if miss_in_defs or extra_in_defs:
        raise RuntimeError(f"error_defs_mismatch miss_in_defs={miss_in_defs} extra_in_defs={extra_in_defs}")

    app_dir = repo_root / "backend" / "app"
    bad_literals: list[tuple[str, list[str]]] = []
    for p in _iter_py_files(app_dir):
        if p.name in {"errors.py"}:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        found = sorted([c for c in _extract_e_literals(text) if c in const_codes_set])
        if found:
            bad_literals.append((str(p.relative_to(repo_root)).replace("\\", "/"), found))

    if bad_literals:
        lines = ["raw_error_code_literals_found:"]
        for rel, codes in bad_literals:
            lines.append(f"- {rel}: {codes}")
        raise RuntimeError("\n".join(lines))

    print("ok", f"codes={len(const_codes_set)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
