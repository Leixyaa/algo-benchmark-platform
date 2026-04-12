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
    # 保留字母数字字符，移除常见的后缀和前缀
    # 移除常见的GT后缀
    stem = re.sub(r"_gt$", "", stem)
    stem = re.sub(r"_groundtruth$", "", stem)
    stem = re.sub(r"_reference$", "", stem)
    # 移除常见的输入前缀
    stem = re.sub(r"^input_", "", stem)
    stem = re.sub(r"^src_", "", stem)
    # 提取核心数字部分（处理类似1966_0.9_0.08这样的格式）
    # 尝试匹配连续的数字
    number_match = re.search(r'\d+', stem)
    if number_match:
        return number_match.group(0)
    # 如果没有数字，移除所有非字母数字字符
    return re.sub(r"[^a-z0-9]+", "", stem)


def _pair_token_full(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    if not stem:
        return ""
    stem = re.sub(r"[_-]?(gt|groundtruth|reference|target)$", "", stem)
    stem = re.sub(r"^(input|src|img|image|frame)[_-]?", "", stem)
    stem = re.sub(r"[_-]?(hazy|noisy|blur|blurry|dark|lowlight|lr|lq|input|src)$", "", stem)
    stem = stem.strip("_- ")
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
    
    # 对于较短的字符串，降低匹配阈值
    if max(m, n) < 5 and lcs_len >= 2:
        score = max(score, 3000)
        
    return score


def _best_fuzzy_match(input_name: str, gt_candidates: set[str]) -> str | None:
    input_token = _pair_token_full(input_name)
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
                
    # 降低匹配阈值，提高匹配成功率
    if best_score < 2000:
        return None
        
    return best_name


def find_paired_images(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int | None = 5,
) -> List[PairedImage]:
    """
    在 `backend/data/<owner_id>/<dataset_id>/<input_dirname>` 与 GT 目录间查找可用配对。
    - 最多返回 `limit` 对样本。
    - 目录不存在或无法配对时返回空列表。
    """
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    
    # 检查GT目录是否存在，如果不存在，尝试其他可能的GT目录名称
    if not gt_dir.exists():
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 没有找到GT目录
            return []
    
    if not input_dir.exists():
        return []

    input_files = [p for p in input_dir.rglob("*") if _is_img(p)]
    if not input_files:
        return []

    gt_by_token = {}
    for gp in gt_dir.rglob("*"):
        if not _is_img(gp):
            continue
        k = _pair_token_full(gp.name)
        if not k or k in gt_by_token:
            continue
        gt_by_token[k] = gp
    if not gt_by_token:
        return []

    pairs: List[PairedImage] = []
    used_gt = set()
    scan_cap = max(int(limit) * 5, 50) if limit is not None else len(input_files)
    for ip in sorted(input_files)[:scan_cap]:
        k = _best_fuzzy_match(ip.name, set(gt_by_token.keys()) - used_gt)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_img(gp):
            pairs.append(PairedImage(input_path=ip, gt_path=gp, name=ip.name))
            used_gt.add(k)
            if limit is not None and len(pairs) >= limit:
                break

    return pairs


def find_dehaze_pairs(data_root: Path, owner_id: str, dataset_id: str, limit: int = 5) -> List[PairedImage]:
    return find_paired_images(data_root=data_root, owner_id=owner_id, dataset_id=dataset_id, input_dirname="hazy", gt_dirname="gt", limit=limit)


def count_paired_images(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
) -> int:
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    
    # 检查GT目录是否存在，如果不存在，尝试其他可能的GT目录名称
    if not gt_dir.exists():
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 没有找到GT目录
            return 0
    
    if not input_dir.exists():
        return 0

    gt_keys = {_pair_token_full(p.name) for p in gt_dir.rglob("*") if _is_img(p)}
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
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
    limit: int | None = 5,
) -> List[PairedVideo]:
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    
    # 检查GT目录是否存在，如果不存在，尝试其他可能的GT目录名称
    if not gt_dir.exists():
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 没有找到GT目录
            return []
    
    if not input_dir.exists():
        return []

    input_files = [p for p in input_dir.rglob("*") if _is_video(p)]
    if not input_files:
        return []

    gt_by_token = {}
    for gp in gt_dir.rglob("*"):
        if not _is_video(gp):
            continue
        k = _pair_token_full(gp.name)
        if not k or k in gt_by_token:
            continue
        gt_by_token[k] = gp
    if not gt_by_token:
        return []

    pairs: List[PairedVideo] = []
    used_gt = set()
    scan_cap = max(int(limit) * 5, 50) if limit is not None else len(input_files)
    for ip in sorted(input_files)[:scan_cap]:
        k = _best_fuzzy_match(ip.name, set(gt_by_token.keys()) - used_gt)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_video(gp):
            pairs.append(PairedVideo(input_path=ip, gt_path=gp, name=ip.name))
            used_gt.add(k)
            if limit is not None and len(pairs) >= limit:
                break
    return pairs


def count_paired_videos(
    data_root: Path,
    owner_id: str,
    dataset_id: str,
    input_dirname: str,
    gt_dirname: str = "gt",
) -> int:
    # 尝试使用用户独有的目录结构
    user_dir = data_root / owner_id
    ds_dir = user_dir / dataset_id
    
    # 如果用户目录不存在，尝试使用旧的目录结构（直接在data下）
    if not ds_dir.exists():
        ds_dir = data_root / dataset_id
    
    input_dir = ds_dir / input_dirname
    gt_dir = ds_dir / gt_dirname
    
    # 检查GT目录是否存在，如果不存在，尝试其他可能的GT目录名称
    if not gt_dir.exists():
        possible_gt_dirs = ["groundtruth", "reference", "target"]
        for dir_name in possible_gt_dirs:
            alt_gt_dir = ds_dir / dir_name
            if alt_gt_dir.exists():
                gt_dir = alt_gt_dir
                break
        else:
            # 没有找到GT目录
            return 0
    
    if not input_dir.exists():
        return 0

    gt_keys = {_pair_token_full(p.name) for p in gt_dir.rglob("*") if _is_video(p)}
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
