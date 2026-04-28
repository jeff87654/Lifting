"""Scan S_18 partition dirs for stale checkpoint claims.

For each partition, enumerate expected combos and compare against actual
on-disk per-combo result files. Reports any partitions where a
checkpoint-logged combo has no valid result file on disk.

The new skip policy in lifting_method_fast_v2.g handles these at runtime
by unmarking stale checkpoints and re-running the combo. This script gives
a quick summary so you can decide whether to kill current workers (to pick
up the fix) vs let them finish.
"""
import os, re
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
    """Return (expected_groups, actual_gens_lines) or (None, None) on parse fail."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return None, None
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


# Summarize each partition
def scan():
    parts_with_stale = []
    for d in sorted(os.listdir(BASE)):
        if not d.startswith("["): continue
        dpath = BASE / d
        if not dpath.is_dir(): continue
        part = [int(x) for x in d.strip("[]").split(",")]
        exp = expected_combos(part)
        combo_files = list(dpath.glob("*.g"))
        complete = 0
        incomplete = 0
        for cf in combo_files:
            e, a = parse_combo_file(cf)
            if e is None:
                incomplete += 1
            elif e == a:
                complete += 1
            else:
                incomplete += 1
        missing = exp - (complete + incomplete)
        has_summary = (dpath / "summary.txt").is_file()
        # "stale checkpoint risk" = has summary + missing combos
        # (worker says done but files are absent)
        if has_summary and missing > 0:
            parts_with_stale.append((d, exp, complete, incomplete, missing))

    print(f"{'partition':30} {'exp':>6} {'complete':>10} {'incompl':>8} {'missing':>8}")
    print("-" * 68)
    total_missing = 0
    for d, exp, c, i, m in parts_with_stale:
        print(f"{d:30} {exp:>6} {c:>10} {i:>8} {m:>8}")
        total_missing += m
    print()
    print(f"Partitions with stale-checkpoint risk: {len(parts_with_stale)}")
    print(f"Total missing combo files: {total_missing}")
    print()
    print("NOTE: The new skip policy in lifting_method_fast_v2.g handles these")
    print("      at runtime - checkpoint is re-validated against disk. Workers")
    print("      launched AFTER the fix will recompute missing combos.")


if __name__ == "__main__":
    scan()
