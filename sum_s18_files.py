#!/usr/bin/env python3
"""
sum_s18_files.py — For each S18 partition folder in parallel_s18, compute:
  - sum of '# deduped: N' header lines across .g files (excluding backups)
  - total_classes from summary.txt (if present)
  - manifest.json fpf_count
Show side-by-side. Useful for spotting reporting drift.
"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
S18  = ROOT / "parallel_s18"
MAN  = S18 / "manifest.json"

DED = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)
TOT = re.compile(r"total_classes:\s*(\d+)")


def files_sum(folder: Path):
    total = 0
    n = 0
    for f in folder.iterdir():
        if not (f.is_file() and f.suffix == ".g"):
            continue
        if "backup" in f.name.lower():
            continue
        head = f.read_text(encoding="utf-8", errors="ignore")[:512]
        m = DED.search(head)
        if m:
            total += int(m.group(1))
            n += 1
    return total, n


def summary_total(folder: Path):
    s = folder / "summary.txt"
    if not s.exists():
        return None
    m = TOT.search(s.read_text(encoding="utf-8", errors="ignore"))
    return int(m.group(1)) if m else None


def main():
    manifest = json.loads(MAN.read_text(encoding="utf-8")) if MAN.exists() else {}
    partitions = manifest.get("partitions", {})
    rows = []
    for folder in sorted(S18.iterdir()):
        if not folder.is_dir():
            continue
        if not folder.name.startswith("["):
            continue
        n = folder.name
        fsum, nf = files_sum(folder)
        st = summary_total(folder)
        key = "_".join(n.strip("[]").split(","))
        manent = partitions.get(key, {})
        manct = manent.get("fpf_count")
        manst = manent.get("status")
        rows.append((n, fsum, nf, st, manct, manst))

    print(f"{'partition':<25} {'files_sum':>10} {'#files':>7} {'summary':>9} "
          f"{'manifest_fpf':>14} {'manifest_status':<14}")
    print("-" * 90)
    for r in rows:
        n, fsum, nf, st, mc, ms = r
        print(f"{n:<25} {fsum:>10} {nf:>7} "
              f"{st if st is not None else '--':>9} "
              f"{mc if mc is not None else '--':>14} {ms or '--':<14}")
    print()
    total_files = sum(r[1] for r in rows)
    total_summ  = sum((r[3] or 0) for r in rows)
    print(f"GRAND TOTAL  files_sum={total_files}  summary_sum={total_summ}")


if __name__ == "__main__":
    main()
