"""Cross-check S_18 partition totals across 3 sources:
  A) Per-combo .g files  (sum of # deduped)
  B) summary.txt         (authoritative from all_fpf at partition end)
  C) gens_<part>.txt     (flat list of groups)

Any row where A != B flags potential STALE CHECKPOINT REDO undercount.
"""
import os, re
from pathlib import Path

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
GENS_DIR = BASE / "gens"


def sum_combo_files(pdir):
    total = 0
    for cf in pdir.glob("*.g"):
        try:
            with open(cf, errors="replace") as f:
                for line in f:
                    if line.startswith("# deduped:"):
                        total += int(line.split(":",1)[1].strip())
                        break
                    if line.startswith("["):
                        break
        except OSError:
            pass
    return total


def summary_total(pdir):
    s = pdir / "summary.txt"
    if not s.is_file():
        return None
    with open(s) as f:
        for line in f:
            if line.startswith("total_classes:"):
                try: return int(line.split(":",1)[1].strip())
                except ValueError: return None
    return None


def gens_count(part):
    fname = "gens_" + "_".join(str(x) for x in part) + ".txt"
    f = GENS_DIR / fname
    if not f.is_file():
        return None
    try:
        with open(f, errors="replace") as fh:
            return sum(1 for line in fh if line.strip().startswith("["))
    except OSError:
        return None


print(f"{'partition':22} {'combo_sum':>10} {'summary':>10} {'gens':>10} {'diff':>8}")
print("-" * 66)

discrepancies = []
for d in sorted(os.listdir(BASE)):
    if not d.startswith("["): continue
    pdir = BASE / d
    if not pdir.is_dir(): continue
    part = tuple(int(x) for x in d.strip("[]").split(","))
    A = sum_combo_files(pdir)
    B = summary_total(pdir)
    C = gens_count(part)
    diff = (B - A) if B is not None else None
    marker = ""
    if B is not None and A != B:
        marker = f"  <-- UNDER by {B - A}"
        discrepancies.append((d, A, B, C, B - A))
    print(f"{d:22} {A:>10} {str(B) if B is not None else '-':>10} "
          f"{str(C) if C is not None else '-':>10} "
          f"{str(diff) if diff is not None else '-':>8}{marker}")

print()
if discrepancies:
    total_under = sum(d[4] for d in discrepancies)
    print(f"UNDERCOUNT: {len(discrepancies)} partitions, total {total_under} classes missed from combo-sum")
else:
    print("No undercounts detected.")
