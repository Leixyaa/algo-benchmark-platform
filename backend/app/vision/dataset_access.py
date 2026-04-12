# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .dataset_io import (
    IMG_EXTS,
    VIDEO_EXTS,
    PairedImage,
    PairedVideo,
    count_paired_images as _count_paired_images,
    count_paired_videos as _count_paired_videos,
    find_paired_images as _find_paired_images,
    find_paired_videos as _find_paired_videos,
)


def resolve_dataset_dir(data_root: Path, owner_id: str, dataset_id: str, storage_path: str | None = None) -> Path:
    if str(storage_path or "").strip():
        return Path(str(storage_path).strip())
    user_dir = data_root / str(owner_id or "system")
    ds_dir = user_dir / dataset_id
    if ds_dir.exists():
        return ds_dir
    legacy_dir = data_root / dataset_id
    if legacy_dir.exists():
        return legacy_dir
    return ds_dir


def find_paired_images(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int | None = 5,
    storage_path: str | None = None,
) -> list[PairedImage]:
    if not str(storage_path or "").strip():
        return _find_paired_images(
            data_root=data_root,
            owner_id=owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname=gt_dirname,
            limit=limit,
        )
    ds_dir = resolve_dataset_dir(data_root, owner_id, dataset_id, storage_path)
    return _find_paired_images(
        data_root=ds_dir.parent,
        owner_id="",
        dataset_id=ds_dir.name,
        input_dirname=input_dirname,
        gt_dirname=gt_dirname,
        limit=limit,
    )


def count_paired_images(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    storage_path: str | None = None,
) -> int:
    if not str(storage_path or "").strip():
        return _count_paired_images(
            data_root=data_root,
            owner_id=owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname=gt_dirname,
        )
    ds_dir = resolve_dataset_dir(data_root, owner_id, dataset_id, storage_path)
    return _count_paired_images(
        data_root=ds_dir.parent,
        owner_id="",
        dataset_id=ds_dir.name,
        input_dirname=input_dirname,
        gt_dirname=gt_dirname,
    )


def find_paired_videos(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int | None = 5,
    storage_path: str | None = None,
) -> list[PairedVideo]:
    if not str(storage_path or "").strip():
        return _find_paired_videos(
            data_root=data_root,
            owner_id=owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname=gt_dirname,
            limit=limit,
        )
    ds_dir = resolve_dataset_dir(data_root, owner_id, dataset_id, storage_path)
    return _find_paired_videos(
        data_root=ds_dir.parent,
        owner_id="",
        dataset_id=ds_dir.name,
        input_dirname=input_dirname,
        gt_dirname=gt_dirname,
        limit=limit,
    )


def count_paired_videos(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    storage_path: str | None = None,
) -> int:
    if not str(storage_path or "").strip():
        return _count_paired_videos(
            data_root=data_root,
            owner_id=owner_id,
            dataset_id=dataset_id,
            input_dirname=input_dirname,
            gt_dirname=gt_dirname,
        )
    ds_dir = resolve_dataset_dir(data_root, owner_id, dataset_id, storage_path)
    return _count_paired_videos(
        data_root=ds_dir.parent,
        owner_id="",
        dataset_id=ds_dir.name,
        input_dirname=input_dirname,
        gt_dirname=gt_dirname,
    )
