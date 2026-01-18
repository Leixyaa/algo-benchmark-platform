from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class DehazePair:
    hazy_path: Path
    gt_path: Path


def _is_img(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMG_EXTS


def find_dehaze_pairs(data_root: Path, dataset_id: str, limit: int = 5) -> List[DehazePair]:
    """
    在 backend/data/<dataset_id>/hazy 与 gt 中找同名文件配对
    - 返回最多 limit 对
    - 找不到则返回 []
    """
    ds_dir = data_root / dataset_id
    hazy_dir = ds_dir / "hazy"
    gt_dir = ds_dir / "gt"
    if not hazy_dir.exists() or not gt_dir.exists():
        return []

    hazy_files = [p for p in hazy_dir.rglob("*") if _is_img(p)]
    if not hazy_files:
        return []

    # 按相对路径/文件名匹配：优先匹配同名文件
    pairs: List[DehazePair] = []
    for hp in sorted(hazy_files)[: max(limit * 5, 50)]:  # 多扫一点避免前面不匹配
        gp = gt_dir / hp.name
        if gp.exists() and _is_img(gp):
            pairs.append(DehazePair(hazy_path=hp, gt_path=gp))
            if len(pairs) >= limit:
                break

    return pairs
