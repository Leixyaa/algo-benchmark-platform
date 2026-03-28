# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@dataclass
class PairedImage:
    input_path: Path
    gt_path: Path
    name: str


@dataclass
class PairedVideo:
    input_path: Path
    gt_path: Path
    name: str


def _is_img(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMG_EXTS


def _is_video(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in VIDEO_EXTS


def find_paired_images(
    data_root: Path,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int = 5,
) -> List[PairedImage]:
    """
    ?? backend/data/<dataset_id>/<input_dirname> ?? <gt_dirname> ?????????????
    - ????? limit ??
    - ?????????? []
    """
    ds_dir = data_root / dataset_id
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    if not input_dir.exists() or not gt_dir.exists():
        return []

    input_files = [p for p in input_dir.rglob("*") if _is_img(p)]
    if not input_files:
        return []

    # ???????????? gt/ ???????????
    pairs: List[PairedImage] = []
    for ip in sorted(input_files)[: max(limit * 5, 50)]:
        gp = gt_dir / ip.name
        if gp.exists() and _is_img(gp):
            pairs.append(PairedImage(input_path=ip, gt_path=gp, name=ip.name))
            if len(pairs) >= limit:
                break

    return pairs


def find_dehaze_pairs(data_root: Path, dataset_id: str, limit: int = 5) -> List[PairedImage]:
    return find_paired_images(data_root=data_root, dataset_id=dataset_id, input_dirname="hazy", gt_dirname="gt", limit=limit)


def count_paired_images(
    data_root: Path,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
) -> int:
    ds_dir = data_root / dataset_id
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    if not input_dir.exists() or not gt_dir.exists():
        return 0

    gt_names = {p.name for p in gt_dir.rglob("*") if _is_img(p)}
    if not gt_names:
        return 0

    n = 0
    for ip in input_dir.rglob("*"):
        if not _is_img(ip):
            continue
        if ip.name in gt_names:
            n += 1
    return n


def find_paired_videos(
    data_root: Path,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int = 5,
) -> List[PairedVideo]:
    ds_dir = data_root / dataset_id
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    if not input_dir.exists() or not gt_dir.exists():
        return []

    input_files = [p for p in input_dir.rglob("*") if _is_video(p)]
    if not input_files:
        return []

    pairs: List[PairedVideo] = []
    for ip in sorted(input_files)[: max(limit * 5, 50)]:
        gp = gt_dir / ip.name
        if gp.exists() and _is_video(gp):
            pairs.append(PairedVideo(input_path=ip, gt_path=gp, name=ip.name))
            if len(pairs) >= limit:
                break
    return pairs


def count_paired_videos(
    data_root: Path,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
) -> int:
    ds_dir = data_root / dataset_id
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    if not input_dir.exists() or not gt_dir.exists():
        return 0

    gt_names = {p.name for p in gt_dir.rglob("*") if _is_video(p)}
    if not gt_names:
        return 0

    n = 0
    for ip in input_dir.rglob("*"):
        if not _is_video(ip):
            continue
        if ip.name in gt_names:
            n += 1
    return n
