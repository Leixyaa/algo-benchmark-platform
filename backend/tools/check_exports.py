# -*- coding: utf-8 -*-
from __future__ import annotations

import zipfile
from pathlib import Path


def _md_summary(p: Path) -> dict:
    raw = p.read_text(encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    colon = "\uFF1A"  # '£º'
    k_task = "- \u4EFB\u52A1\u7C7B\u578B" + colon
    k_ds = "- \u6570\u636E\u96C6" + colon
    k_rec = "\u63A8\u8350\u7B97\u6CD5" + colon
    task = next((ln.split(colon, 1)[1] for ln in lines if ln.startswith(k_task)), None)
    dataset = next((ln.split(colon, 1)[1] for ln in lines if ln.startswith(k_ds)), None)
    top = next((ln for ln in lines if ln.startswith(k_rec)), None)
    run_ids = []
    for ln in lines:
        if ln.startswith("|") and ln.endswith("|") and "RunID" not in ln:
            parts = [x.strip() for x in ln.strip("|").split("|")]
            if len(parts) >= 9:
                rid = parts[-1]
                if rid and rid not in {"RunID", "---"}:
                    run_ids.append(rid)
    return {"task": task, "dataset": dataset, "recommend": top, "run_ids": run_ids[:10]}


def _xlsx_summary(p: Path) -> dict:
    z = zipfile.ZipFile(p)
    names = z.namelist()
    sheets = [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
    has_ss = "xl/sharedStrings.xml" in names
    first_sheet_bytes = len(z.read(sheets[0])) if sheets else 0
    z.close()
    return {"worksheets": len(sheets), "has_sharedStrings": has_ss, "sheet1_xml_bytes": first_sheet_bytes}


def main() -> int:
    base = Path("d:/algo-benchmark-platform/docs/\u5BFC\u51FA\u6587\u4EF6")
    if not base.exists():
        print("missing:", base)
        return 1

    mds = sorted(base.rglob("compare_conclusion_*.md"))
    xlsxs = sorted(base.rglob("compare_recommend_*.xlsx"))

    print("md_count", len(mds))
    for p in mds:
        s = _md_summary(p)
        print("MD", p.relative_to(base).as_posix(), "task", s["task"], "dataset", s["dataset"], "runs", len(s["run_ids"]))

    print("xlsx_count", len(xlsxs))
    for p in xlsxs:
        s = _xlsx_summary(p)
        print("XLSX", p.relative_to(base).as_posix(), "worksheets", s["worksheets"], "sheet1_bytes", s["sheet1_xml_bytes"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
