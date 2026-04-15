# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import re


IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# RESIDE 等常用 clear/ 作为无雾真值；与 gt/ 等价参与配对与扫描
_FALLBACK_GT_DIR_NAMES = ("groundtruth", "reference", "target", "clear")


def resolve_gt_dir_under(ds_dir: Path, primary: str = "gt") -> Path | None:
    primary_path = ds_dir / primary
    if primary_path.is_dir():
        return primary_path
    for name in _FALLBACK_GT_DIR_NAMES:
        alt = ds_dir / name
        if alt.is_dir():
            return alt
    return None


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


def _pair_number_token(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    if not stem:
        return ""
    m = re.search(r"\d+", stem)
    return m.group(0) if m else ""


def _pair_token_full(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    if not stem:
        return ""
    stem = re.sub(r"[_-]?(gt|groundtruth|reference|target)$", "", stem)
    stem = re.sub(r"^(input|src|img|image|frame)[_-]?", "", stem)
    stem = re.sub(r"[_-]?(hazy|noisy|blur|blurry|dark|lowlight|lr|lq|input|src)$", "", stem)
    stem = stem.strip("_- ")
    # RESIDE SOTS indoor (nyuhaze500)：1400_1 / 1400_10 等同一场景，对应 GT 1400.png
    if re.fullmatch(r"\d+_\d+", stem):
        stem = stem.rsplit("_", 1)[0]
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
            
    # 保持较高阈值，避免不同样本被错误配对导致指标失真
    if best_score < 7000:
        return None
        
    return best_name


def _pick_gt_token(
    input_name: str,
    gt_tokens: set[str],
    gt_by_number_unique: dict[str, str],
    *,
    allow_fuzzy: bool,
) -> str | None:
    full = _pair_token_full(input_name)
    if full and full in gt_tokens:
        return full
    number = _pair_number_token(input_name)
    if number and number in gt_by_number_unique:
        return gt_by_number_unique[number]
    if not allow_fuzzy:
        return None
    return _best_fuzzy_match(input_name, gt_tokens)


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
    gt_dir = resolve_gt_dir_under(ds_dir, gt_dirname)
    if gt_dir is None:
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
    gt_tokens = set(gt_by_token.keys())
    gt_by_number: dict[str, list[str]] = {}
    for token in gt_tokens:
        m = re.search(r"\d+", token)
        if not m:
            continue
        gt_by_number.setdefault(m.group(0), []).append(token)
    gt_by_number_unique = {k: v[0] for k, v in gt_by_number.items() if len(v) == 1}

    pairs: List[PairedImage] = []
    scan_cap = max(int(limit) * 5, 50) if limit is not None else len(input_files)
    for ip in sorted(input_files)[:scan_cap]:
        k = _pick_gt_token(ip.name, gt_tokens, gt_by_number_unique, allow_fuzzy=True)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_img(gp):
            pairs.append(PairedImage(input_path=ip, gt_path=gp, name=ip.name))
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
    gt_dir = resolve_gt_dir_under(ds_dir, gt_dirname)
    if gt_dir is None:
        return 0

    if not input_dir.exists():
        return 0

    gt_keys = {_pair_token_full(p.name) for p in gt_dir.rglob("*") if _is_img(p)}
    gt_keys.discard("")
    if not gt_keys:
        return 0
    gt_by_number: dict[str, list[str]] = {}
    for token in gt_keys:
        m = re.search(r"\d+", token)
        if not m:
            continue
        gt_by_number.setdefault(m.group(0), []).append(token)
    gt_by_number_unique = {k: v[0] for k, v in gt_by_number.items() if len(v) == 1}

    n = 0
    for ip in input_dir.rglob("*"):
        if not _is_img(ip):
            continue
        # 计数阶段默认禁用模糊匹配，避免预览模式因全量模糊扫描导致耗时过长
        k = _pick_gt_token(ip.name, gt_keys, gt_by_number_unique, allow_fuzzy=False)
        if k:
            n += 1
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
    gt_dir = resolve_gt_dir_under(ds_dir, gt_dirname)
    if gt_dir is None:
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
    gt_tokens = set(gt_by_token.keys())
    gt_by_number: dict[str, list[str]] = {}
    for token in gt_tokens:
        m = re.search(r"\d+", token)
        if not m:
            continue
        gt_by_number.setdefault(m.group(0), []).append(token)
    gt_by_number_unique = {k: v[0] for k, v in gt_by_number.items() if len(v) == 1}

    pairs: List[PairedVideo] = []
    scan_cap = max(int(limit) * 5, 50) if limit is not None else len(input_files)
    for ip in sorted(input_files)[:scan_cap]:
        k = _pick_gt_token(ip.name, gt_tokens, gt_by_number_unique, allow_fuzzy=True)
        gp = gt_by_token.get(k) if k else None
        if gp is not None and gp.exists() and _is_video(gp):
            pairs.append(PairedVideo(input_path=ip, gt_path=gp, name=ip.name))
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
    gt_dir = resolve_gt_dir_under(ds_dir, gt_dirname)
    if gt_dir is None:
        return 0

    if not input_dir.exists():
        return 0

    gt_keys = {_pair_token_full(p.name) for p in gt_dir.rglob("*") if _is_video(p)}
    gt_keys.discard("")
    if not gt_keys:
        return 0
    gt_by_number: dict[str, list[str]] = {}
    for token in gt_keys:
        m = re.search(r"\d+", token)
        if not m:
            continue
        gt_by_number.setdefault(m.group(0), []).append(token)
    gt_by_number_unique = {k: v[0] for k, v in gt_by_number.items() if len(v) == 1}

    n = 0
    for ip in input_dir.rglob("*"):
        if not _is_video(ip):
            continue
        k = _pick_gt_token(ip.name, gt_keys, gt_by_number_unique, allow_fuzzy=False)
        if k:
            n += 1
    return n
