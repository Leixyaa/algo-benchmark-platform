# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import re


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


def _pair_token(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    if not stem:
        return ""
    # 保留字母数字字符，同时允许一些常见的分隔符
    return re.sub(r"[^a-z0-9]+", "", stem)


def _fuzzy_match_score(a: str, b: str) -> int:
    """
    计算两个标记之间的模糊匹配得分。
    使用最长公共子序列（LCS）算法。
    """
    if not a or not b:
        return 0
    if a == b:
        return 10_000
    
    m, n = len(a), len(b)
    # LCS 动态规划
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
                
    lcs_len = dp[m][n]
    
    # 匹配长度太短则认为无效
    if lcs_len < 1:
        return 0
        
    # 计算匹配得分：(LCS长度) / max(A长度, B长度) * 10000
    # 这样如果一个是另一个的子序列，得分就是其在较长者中的占比
    score = (lcs_len * 10000) // max(m, n)
    return score


def _best_fuzzy_match(input_name: str, gt_candidates: set[str]) -> str | None:
    input_token = _pair_token(input_name)
    if not input_token or not gt_candidates:
        return None
    
    # 1. 精确匹配优先 (快)
    if input_token in gt_candidates:
        return input_token
    
    # 2. 模糊匹配 (慢)
    best_name = None
    best_score = 0
    for g in gt_candidates:
        score = _fuzzy_match_score(input_token, g)
        if score > best_score:
            best_score = score
            best_name = g
            
    # 如果初步匹配得分不够高（低于 70%），尝试反向匹配
    if not best_name or best_score < 7000:
        for g in gt_candidates:
            score = _fuzzy_match_score(g, input_token)
            if score > best_score:
                best_score = score
                best_name = g
    
    # 设定最低匹配阈值。3000 表示大约 30% 的相似度，这在文件名匹配中通常是安全的
    # 尤其能处理 1.png 与 1_gt.png 的情况（1/3 = 33%）
    if best_score < 3000:
        return None
        
    return best_name


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

    gt_by_token = {}
    for gp in gt_dir.rglob("*"):
        if not _is_img(gp):
            continue
        k = _pair_token(gp.name)
        if not k or k in gt_by_token:
            continue
        gt_by_token[k] = gp
    if not gt_by_token:
        return []

    pairs: List[PairedImage] = []
    used_gt = set()
    for ip in sorted(input_files)[: max(limit * 5, 50)]:
        k = _best_fuzzy_match(ip.name, set(gt_by_token.keys()) - used_gt)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_img(gp):
            pairs.append(PairedImage(input_path=ip, gt_path=gp, name=ip.name))
            used_gt.add(k)
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

    gt_keys = {_pair_token(p.name) for p in gt_dir.rglob("*") if _is_img(p)}
    gt_keys.discard("")
    if not gt_keys:
        return 0

    n = 0
    used_gt = set()
    for ip in input_dir.rglob("*"):
        if not _is_img(ip):
            continue
        k = _best_fuzzy_match(ip.name, gt_keys - used_gt)
        if k:
            n += 1
            used_gt.add(k)
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

    gt_by_token = {}
    for gp in gt_dir.rglob("*"):
        if not _is_video(gp):
            continue
        k = _pair_token(gp.name)
        if not k or k in gt_by_token:
            continue
        gt_by_token[k] = gp
    if not gt_by_token:
        return []

    pairs: List[PairedVideo] = []
    used_gt = set()
    for ip in sorted(input_files)[: max(limit * 5, 50)]:
        k = _best_fuzzy_match(ip.name, set(gt_by_token.keys()) - used_gt)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_video(gp):
            pairs.append(PairedVideo(input_path=ip, gt_path=gp, name=ip.name))
            used_gt.add(k)
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

    gt_keys = {_pair_token(p.name) for p in gt_dir.rglob("*") if _is_video(p)}
    gt_keys.discard("")
    if not gt_keys:
        return 0

    n = 0
    used_gt = set()
    for ip in input_dir.rglob("*"):
        if not _is_video(ip):
            continue
        k = _best_fuzzy_match(ip.name, gt_keys - used_gt)
        if k:
            n += 1
            used_gt.add(k)
    return n
