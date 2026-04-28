"""Authoritative S_18 status from disk, ignoring summary.txt and worker reports.

For each partition:
  - expected combos (from block multiplicities × TG library sizes)
  - actual valid combo files (# deduped matches [ lines)
  - sum of deduped counts from valid combo files
"""
import os
from pathlib import Path
from collections import Counter
from math import comb

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
TG_COUNT = {2:1,3:2,4:5,5:5,6:16,7:7,8:50,9:34,10:45,11:8,12:301,13:9,14:63,15:104,16:1954,17:10,18:983}


def expected_combos(part):
    bc = Counter(part)
    total = 1
    for s, m in bc.items():
        total *= comb(TG_COUNT[s] + m - 1, m)
    return total


def parse_combo_file(path):
    """Return (expected, actual) from combo file header+body, or (None, 0) on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return None, 0
    expected = None
    actual = 0
    for line in data.splitlines():
        s = line.rstrip()
        if s.startswith("# deduped:"):
            try:
                expected = int(s.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif s.startswith("["):
            actual += 1
    return expected, actual


rows = []
grand_expected = 0
grand_complete = 0
grand_incomplete = 0
grand_missing = 0
grand_fpf = 0

for d in sorted(os.listdir(BASE)):
    if not d.startswith("["): continue
    dpath = BASE / d
    if not dpath.is_dir(): continue
    part = [int(x) for x in d.strip("[]").split(",")]
    exp = expected_combos(part)
    complete = 0
    incomplete = 0
    fpf_count = 0
    for cf in dpath.glob("*.g"):
        e, a = parse_combo_file(cf)
        if e is not None and e == a:
            complete += 1
            fpf_count += a
        else:
            incomplete += 1
    missing = exp - (complete + incomplete)
    rows.append((d, exp, complete, incomplete, missing, fpf_count))
    grand_expected += exp
    grand_complete += complete
    grand_incomplete += incomplete
    grand_missing += missing
    grand_fpf += fpf_count

rows.sort(key=lambda r: r[4] + r[3], reverse=True)  # most remaining work first

print(f"{'partition':30} {'exp':>6} {'done':>6} {'incomp':>7} {'miss':>6} {'fpf':>10}")
print("-" * 72)
for r in rows:
    print(f"{r[0]:30} {r[1]:>6} {r[2]:>6} {r[3]:>7} {r[4]:>6} {r[5]:>10}")

print("-" * 72)
remaining = grand_missing + grand_incomplete
print(f"{'TOTAL':30} {grand_expected:>6} {grand_complete:>6} "
      f"{grand_incomplete:>7} {grand_missing:>6} {grand_fpf:>10}")
print()
print(f"Partitions: {len(rows)}")
print(f"Combos: {grand_complete}/{grand_expected} complete  "
      f"({100*grand_complete/grand_expected:.1f}%)")
print(f"Remaining: {remaining} combos ({grand_missing} never started, "
      f"{grand_incomplete} incomplete)")
print(f"FPF classes on disk: {grand_fpf:,}")
print(f"Inherited from S_17: 1,466,358")
print(f"S_18 target (A000638(18)): 7,274,651")
print(f"  -> FPF target = 7,274,651 - 1,466,358 = 5,808,293")
print(f"  -> current {grand_fpf:,} = {100*grand_fpf/5808293:.1f}% of FPF target")
