#!/usr/bin/env python3
"""
show_predictions.py — Read all predict_s18_tmp/<lambda>/result.json files,
cross-reference with parallel_s18/<lambda+2>/ summary.txt and combo file
'# deduped:' headers, and print a rigid vs non-rigid comparison table.

Run anytime to see current state, even while predict_s18_from_s16.py is still
running new partitions.
"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TMP  = ROOT / "predict_s18_tmp"
S18  = ROOT / "parallel_s18"

DED = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)
TOT = re.compile(r"total_classes:\s*(\d+)")


def s18_name(s16: str) -> str:
    parts = sorted([int(x) for x in s16.strip("[]").split(",")] + [2], reverse=True)
    return "[" + ",".join(str(p) for p in parts) + "]"


def is_rigid(s16: str) -> bool:
    return 2 not in [int(x) for x in s16.strip("[]").split(",")]


def actual(s18_part: str):
    folder = S18 / s18_part
    if not folder.is_dir():
        return None, None
    fsum = 0
    for f in folder.iterdir():
        if not (f.is_file() and f.suffix == ".g"): continue
        if "backup" in f.name.lower(): continue
        head = f.read_text(encoding="utf-8", errors="ignore")[:512]
        m = DED.search(head)
        if m:
            fsum += int(m.group(1))
    summ = folder / "summary.txt"
    summt = None
    if summ.exists():
        m = TOT.search(summ.read_text(encoding="utf-8", errors="ignore"))
        if m: summt = int(m.group(1))
    return fsum, summt


def main():
    rows = []
    for d in sorted(TMP.iterdir()):
        if not d.is_dir(): continue
        rj = d / "result.json"
        if not rj.exists(): continue
        r = json.loads(rj.read_text())
        s16 = r["partition"]
        s18 = s18_name(s16)
        rig = is_rigid(s16)
        fsum, summt = actual(s18)
        rows.append({
            "s16": s16,
            "s18": s18,
            "rigid": rig,
            "subs": r["subgroup_count"],
            "predicted": r["predicted"],
            "summary": summt,
            "files_sum": fsum,
            "delta_summary": (r["predicted"] - summt) if (summt is not None and r["predicted"]) else None,
            "delta_files":   (r["predicted"] - fsum)  if (fsum  is not None and r["predicted"]) else None,
            "elapsed_s": r.get("elapsed_s"),
        })

    rows.sort(key=lambda x: (not x["rigid"], x["s16"]))

    print(f"{'rig':<3} {'S16':<22} {'S18':<22} {'#H':>6} {'predicted':>10} "
          f"{'summary':>9} {'files_sum':>9} {'d_summ':>7} {'d_files':>7} {'time':>5}")
    print("-" * 110)

    for r in rows:
        marker = ""
        if r["rigid"]:
            if r["delta_summary"] is not None and r["delta_summary"] != 0:
                marker = "  *MISSING(rigid)*"
        else:
            if r["delta_summary"] is not None and r["delta_summary"] < 0:
                marker = "  *under-predicted (S16 may be missing)*"
        print(f"{'Y' if r['rigid'] else 'N':<3} "
              f"{r['s16']:<22} {r['s18']:<22} {r['subs']:>6} {r['predicted']:>10} "
              f"{r['summary'] if r['summary'] is not None else '--':>9} "
              f"{r['files_sum'] if r['files_sum'] is not None else '--':>9} "
              f"{r['delta_summary'] if r['delta_summary'] is not None else '':>7} "
              f"{r['delta_files'] if r['delta_files'] is not None else '':>7} "
              f"{r['elapsed_s']:>5.0f}s{marker}")

    print()
    print("Legend:")
    print("  rig=Y : lambda has no 2-part. Formula gives EXACT count of S18 [..,2] FPF subdirects.")
    print("          Any non-zero d_summ indicates real missing groups (or summary.txt drift).")
    print("  rig=N : lambda already has a 2-part. Formula is UPPER BOUND only —")
    print("          real count is smaller because S_(k+1) symmetry on (k+1) 2-blocks merges lifts.")
    print("          Negative d_summ means S16 itself may be missing groups (formula is upper bound).")


if __name__ == "__main__":
    main()
