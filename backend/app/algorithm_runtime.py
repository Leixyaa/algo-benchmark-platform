# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def _read_image_bgr(path: Path) -> np.ndarray | None:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except Exception:
        data = np.array([], dtype=np.uint8)
    if data.size > 0:
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is not None and image.size > 0:
            return image
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


class AlgorithmRuntimeError(Exception):
    def __init__(self, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = str(message or "algorithm_runtime_error")
        self.detail = detail if isinstance(detail, dict) else {}


@dataclass(frozen=True)
class AlgorithmRuntimeResult:
    image_bgr_u8: np.ndarray
    detail: dict[str, Any]


def _read_first_frame_bgr(path: Path) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(path))
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None or frame.size == 0:
        return None
    return frame


class UserAlgorithmImageRunner:
    def __init__(self, algorithm: dict[str, Any], *, timeout_s: float = 30.0):
        self.algorithm = algorithm if isinstance(algorithm, dict) else {}
        self.archive_path = _resolve_archive_path(self.algorithm)
        self.timeout = max(1.0, float(timeout_s or 30.0))
        self._tmp_ctx = tempfile.TemporaryDirectory(prefix="abp_alg_")
        self._tmp_dir = Path(self._tmp_ctx.name)
        self.script_path = _prepare_script(self.archive_path, self._tmp_dir)
        self._sample_index = 0
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._tmp_ctx.cleanup()
        self._closed = True

    def __enter__(self) -> UserAlgorithmImageRunner:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.close()
        return False

    def run(self, input_bgr_u8: np.ndarray, *, sample_name: str = "") -> AlgorithmRuntimeResult:
        if self._closed:
            raise AlgorithmRuntimeError(
                "algorithm_runtime_closed",
                {"algorithm_id": str((self.algorithm or {}).get("algorithm_id") or "")},
            )
        if input_bgr_u8 is None or not isinstance(input_bgr_u8, np.ndarray) or input_bgr_u8.size == 0:
            raise AlgorithmRuntimeError("algorithm_input_image_invalid", {"sample_name": sample_name})

        self._sample_index += 1
        sample_dir = self._tmp_dir / "samples" / f"sample_{self._sample_index:04d}"
        sample_dir.mkdir(parents=True, exist_ok=True)
        input_path = sample_dir / "input.png"
        output_path = sample_dir / "output.png"
        if not cv2.imwrite(str(input_path), input_bgr_u8):
            raise AlgorithmRuntimeError("algorithm_input_write_failed", {"input_path": str(input_path)})

        cmd = [sys.executable, str(self.script_path), "--input", str(input_path), "--output", str(output_path)]
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        start = time.time()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.script_path.parent),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AlgorithmRuntimeError(
                "algorithm_script_timeout",
                {
                    "timeout_s": self.timeout,
                    "script": str(self.script_path),
                    "stdout": _short_text(exc.stdout or ""),
                    "stderr": _short_text(exc.stderr or ""),
                    "sample_name": sample_name,
                    "sample_index": self._sample_index,
                },
            ) from exc
        elapsed = time.time() - start

        detail = {
            "archive_path": str(self.archive_path),
            "script": str(self.script_path),
            "command": " ".join(cmd),
            "returncode": int(completed.returncode),
            "elapsed_s": round(float(elapsed), 6),
            "stdout": _short_text(completed.stdout),
            "stderr": _short_text(completed.stderr),
            "sample_name": sample_name,
            "sample_index": self._sample_index,
            "mode": "subprocess_reuse_package",
        }
        if completed.returncode != 0:
            raise AlgorithmRuntimeError("algorithm_script_failed", detail)

        resolved_output = _find_output_image(input_path=input_path, output_path=output_path)
        if resolved_output is None:
            detail["output_path"] = str(output_path)
            raise AlgorithmRuntimeError("algorithm_output_missing", detail)
        pred = _read_image_bgr(resolved_output)
        detail["output_path"] = str(resolved_output)
        if pred is None or pred.size == 0:
            raise AlgorithmRuntimeError("algorithm_output_unreadable", detail)
        return AlgorithmRuntimeResult(image_bgr_u8=pred, detail=detail)


class UserAlgorithmVideoRunner:
    def __init__(self, algorithm: dict[str, Any], *, timeout_s: float = 60.0):
        self.algorithm = algorithm if isinstance(algorithm, dict) else {}
        self.archive_path = _resolve_archive_path(self.algorithm)
        self.timeout = max(1.0, float(timeout_s or 60.0))
        self._tmp_ctx = tempfile.TemporaryDirectory(prefix="abp_alg_video_")
        self._tmp_dir = Path(self._tmp_ctx.name)
        self.script_path = _prepare_script(self.archive_path, self._tmp_dir)
        self._sample_index = 0
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._tmp_ctx.cleanup()
        self._closed = True

    def __enter__(self) -> UserAlgorithmVideoRunner:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.close()
        return False

    def run(self, input_video_path: str | Path, *, sample_name: str = "") -> AlgorithmRuntimeResult:
        if self._closed:
            raise AlgorithmRuntimeError(
                "algorithm_runtime_closed",
                {"algorithm_id": str((self.algorithm or {}).get("algorithm_id") or "")},
            )
        source_path = Path(str(input_video_path or "")).resolve()
        if not source_path.exists() or not source_path.is_file():
            raise AlgorithmRuntimeError("algorithm_input_video_missing", {"input_path": str(source_path), "sample_name": sample_name})

        self._sample_index += 1
        sample_dir = self._tmp_dir / "samples" / f"sample_{self._sample_index:04d}"
        sample_dir.mkdir(parents=True, exist_ok=True)
        output_path = sample_dir / "output.mp4"

        cmd = [sys.executable, str(self.script_path), "--input", str(source_path), "--output", str(output_path)]
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        start = time.time()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.script_path.parent),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AlgorithmRuntimeError(
                "algorithm_script_timeout",
                {
                    "timeout_s": self.timeout,
                    "script": str(self.script_path),
                    "stdout": _short_text(exc.stdout or ""),
                    "stderr": _short_text(exc.stderr or ""),
                    "sample_name": sample_name,
                    "sample_index": self._sample_index,
                    "mode": "subprocess_video",
                },
            ) from exc
        elapsed = time.time() - start

        detail = {
            "archive_path": str(self.archive_path),
            "script": str(self.script_path),
            "command": " ".join(cmd),
            "returncode": int(completed.returncode),
            "elapsed_s": round(float(elapsed), 6),
            "stdout": _short_text(completed.stdout),
            "stderr": _short_text(completed.stderr),
            "sample_name": sample_name,
            "sample_index": self._sample_index,
            "mode": "subprocess_video",
            "input_path": str(source_path),
        }
        if completed.returncode != 0:
            raise AlgorithmRuntimeError("algorithm_script_failed", detail)

        resolved_output = _find_output_video(output_path=output_path)
        if resolved_output is None:
            detail["output_path"] = str(output_path)
            raise AlgorithmRuntimeError("algorithm_output_missing", detail)
        pred = _read_first_frame_bgr(resolved_output)
        detail["output_path"] = str(resolved_output)
        if pred is None or pred.size == 0:
            raise AlgorithmRuntimeError("algorithm_output_unreadable", detail)
        return AlgorithmRuntimeResult(image_bgr_u8=pred, detail=detail)


def _short_text(value: str, limit: int = 3000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _is_image_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTS


def _safe_extract_zip(package_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    try:
        with zipfile.ZipFile(package_path) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name or name.endswith("/"):
                    continue
                if name.startswith("/") or name.startswith("../") or "/../" in name:
                    raise AlgorithmRuntimeError("algorithm_package_path_traversal", {"path": name})
                out_path = (dest_resolved / name).resolve()
                if out_path != dest_resolved and dest_resolved not in out_path.parents:
                    raise AlgorithmRuntimeError("algorithm_package_path_traversal", {"path": name})
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
    except zipfile.BadZipFile as exc:
        raise AlgorithmRuntimeError("algorithm_package_bad_zip", {"archive_path": str(package_path)}) from exc


def _pick_script_from_dir(root: Path) -> Path:
    scripts = sorted(
        (p for p in root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts),
        key=lambda p: str(p.relative_to(root)).lower(),
    )
    infer_scripts = [p for p in scripts if p.name.lower() == "infer.py"]
    if infer_scripts:
        return sorted(infer_scripts, key=lambda p: (len(p.relative_to(root).parts), str(p.relative_to(root)).lower()))[0]
    if len(scripts) == 1:
        return scripts[0]
    if not scripts:
        raise AlgorithmRuntimeError("algorithm_script_missing", {"expected": "infer.py or single .py file"})
    raise AlgorithmRuntimeError(
        "algorithm_script_ambiguous",
        {"python_files": [str(p.relative_to(root)) for p in scripts[:20]]},
    )


def _prepare_script(package_path: Path, work_dir: Path) -> Path:
    suffix = package_path.suffix.lower()
    if suffix == ".py":
        return package_path.resolve()
    if suffix == ".zip":
        extract_dir = work_dir / "package"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract_zip(package_path, extract_dir)
        return _pick_script_from_dir(extract_dir)
    raise AlgorithmRuntimeError(
        "algorithm_package_unsupported",
        {"archive_path": str(package_path), "supported": [".py", ".zip"]},
    )


def _resolve_archive_path(algorithm: dict[str, Any]) -> Path:
    archive_path = Path(str((algorithm or {}).get("archive_path") or "").strip())
    if archive_path and archive_path.exists() and archive_path.is_file():
        return archive_path.resolve()
    raise AlgorithmRuntimeError(
        "algorithm_package_missing",
        {
            "algorithm_id": str((algorithm or {}).get("algorithm_id") or ""),
            "archive_path": str(archive_path) if str(archive_path) else "",
        },
    )


def _find_output_image(input_path: Path, output_path: Path) -> Path | None:
    input_resolved = input_path.resolve()
    if _is_image_path(output_path):
        return output_path.resolve()

    candidates: list[Path] = []
    if output_path.is_dir():
        candidates.extend(sorted((p for p in output_path.rglob("*") if _is_image_path(p)), key=lambda p: str(p).lower()))

    deduped: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        resolved = item.resolve()
        key = str(resolved).lower()
        if key in seen or resolved == input_resolved:
            continue
        seen.add(key)
        deduped.append(resolved)
    if not deduped:
        return None
    same_name = [p for p in deduped if p.name.lower() == input_path.name.lower()]
    return same_name[0] if same_name else deduped[0]


def _find_output_video(output_path: Path) -> Path | None:
    if output_path.is_file() and output_path.suffix.lower() in VIDEO_EXTS:
        return output_path.resolve()
    candidates: list[Path] = []
    if output_path.is_dir():
        candidates.extend(sorted((p for p in output_path.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS), key=lambda p: str(p).lower()))
    parent = output_path.parent
    if parent.exists():
        candidates.extend(sorted((p for p in parent.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS), key=lambda p: str(p).lower()))
    deduped: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        resolved = item.resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped[0] if deduped else None


def execute_user_algorithm_image(
    algorithm: dict[str, Any],
    input_bgr_u8: np.ndarray,
    *,
    timeout_s: float = 30.0,
    sample_name: str = "",
) -> AlgorithmRuntimeResult:
    with UserAlgorithmImageRunner(algorithm, timeout_s=timeout_s) as runner:
        return runner.run(input_bgr_u8, sample_name=sample_name)
