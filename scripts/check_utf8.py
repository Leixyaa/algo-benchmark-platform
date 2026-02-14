from __future__ import annotations

import sys
from pathlib import Path


def iter_files(root: Path) -> list[Path]:
    exts = {".py", ".js", ".ts", ".vue", ".css", ".md", ".json", ".ps1", ".cmd"}
    skip_dirs = {".git", "node_modules", ".venv", "dist", "build", "__pycache__"}
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_dir() and p.name in skip_dirs:
            continue
        if p.is_file() and p.suffix.lower() in exts:
            if any(part in skip_dirs for part in p.parts):
                continue
            files.append(p)
    return files


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    bad: list[tuple[Path, int, int]] = []
    for p in iter_files(root):
        b = p.read_bytes()
        try:
            b.decode("utf-8")
        except UnicodeDecodeError as e:
            bad.append((p, e.start, b[e.start]))
    if not bad:
        print("OK: all checked files are valid UTF-8")
        return 0
    print("NOT UTF-8:")
    for p, pos, byte in bad:
        rel = p.relative_to(root)
        print(f"- {rel} (pos {pos}, byte 0x{byte:02x})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

