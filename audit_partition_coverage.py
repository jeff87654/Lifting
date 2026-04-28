"""audit_partition_coverage.py — for each S_n FPF partition, compute the
expected number of combo files via NrTransitiveGroups + multiset coefficients,
compare to actual files on disk in parallel_sn_v2/<n>/<part>/, and report
missing combos.

Usage:
    python audit_partition_coverage.py 18
    python audit_partition_coverage.py 18 --list-missing      # also dump missing combo names
"""
from __future__ import annotations
import argparse
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
SN_DIR = ROOT / "parallel_sn_v2"

# NrTransitiveGroups(n) for n=2..30 — from GAP's TransitiveGroups library
NTG = {
    2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50, 9: 34, 10: 45,
    11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954, 17: 10, 18: 983,
    19: 8, 20: 1117,
}


def fpf_partitions(n: int):
    """All partitions of n with every part >= 2, descending."""
    def gen(rem, max_part):
        if rem == 0:
            yield ()
            return
        for p in range(min(rem, max_part), 1, -1):
            if p > rem:
                continue
            for rest in gen(rem - p, p):
                yield (p,) + rest
    return list(gen(n, n))


def expected_combos(partition):
    """Number of unique multisets of (d, t) consistent with partition.
    For each distinct part d with multiplicity m: multiset(NTG(d), m).
    Multiset coefficient: C(N+m-1, m).
    """
    parts = Counter(partition)
    total = 1
    for d, m in parts.items():
        n_choices = NTG[d]
        total *= math.comb(n_choices + m - 1, m)
    return total


COMBO_RE = re.compile(r"^\[(\d+),\d+\](?:_\[(\d+),\d+\])*\.g$")


def count_combo_files(part_dir: Path) -> int:
    if not part_dir.exists():
        return 0
    return sum(1 for p in part_dir.iterdir() if p.suffix == ".g" and p.name.startswith("["))


def list_combo_files(part_dir: Path):
    if not part_dir.exists():
        return set()
    return {p.stem for p in part_dir.iterdir() if p.suffix == ".g" and p.name.startswith("[")}


def enumerate_combos(partition):
    """Generate all canonical combo strings for a partition.
    A combo is an assignment of t_i in 1..NTG(d_i) for each part d_i, with
    the constraint that within each block of equal parts, the t-list is
    weakly increasing (canonical multiset rep).
    """
    parts = Counter(partition)
    # Build's filename convention: parts ASCENDING by degree, then t-values
    # ascending within each block of equal parts.
    distinct_parts = sorted(parts.items(), key=lambda kv: kv[0])

    def gen_block(d, m):
        if m == 0:
            yield ()
            return
        n = NTG[d]
        def rec(remaining, min_t):
            if remaining == 0:
                yield ()
                return
            for t in range(min_t, n + 1):
                for tail in rec(remaining - 1, t):
                    yield (t,) + tail
        for ts in rec(m, 1):
            yield ts

    def gen_all(idx):
        if idx == len(distinct_parts):
            yield []
            return
        d, m = distinct_parts[idx]
        for ts in gen_block(d, m):
            block = [(d, t) for t in ts]
            for rest in gen_all(idx + 1):
                yield block + rest

    for combo in gen_all(0):
        s = "_".join(f"[{d},{t}]" for d, t in combo)
        yield s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--list-missing", action="store_true",
                    help="dump names of missing combos per partition")
    ap.add_argument("--max-list", type=int, default=10,
                    help="max missing combos per partition to list (default 10)")
    args = ap.parse_args()

    n = args.n
    n_dir = SN_DIR / str(n)
    if not n_dir.exists():
        print(f"ERROR: {n_dir} does not exist")
        sys.exit(1)

    parts = fpf_partitions(n)
    total_expected = 0
    total_present = 0
    rows = []
    for partition in parts:
        part_str = "[" + ",".join(str(p) for p in partition) + "]"
        part_dir = n_dir / part_str
        expected = expected_combos(partition)
        present = count_combo_files(part_dir)
        total_expected += expected
        total_present += present
        diff = expected - present
        rows.append((part_str, expected, present, diff))

    # Sort by largest gap first
    rows.sort(key=lambda r: -r[3])

    print(f"=== S{n} partition coverage audit ===")
    print(f"{'partition':<28} {'expected':>10} {'present':>10} {'missing':>10}")
    print("-" * 60)
    for part_str, expected, present, diff in rows:
        marker = "  X" if diff > 0 else ("  ?" if diff < 0 else "")
        print(f"{part_str:<28} {expected:>10} {present:>10} {diff:>10}{marker}")
    print("-" * 60)
    print(f"{'TOTAL':<28} {total_expected:>10} {total_present:>10} {total_expected - total_present:>10}")

    if args.list_missing:
        print("\n=== missing combos per partition (up to --max-list each) ===")
        for partition in parts:
            part_str = "[" + ",".join(str(p) for p in partition) + "]"
            part_dir = n_dir / part_str
            expected = expected_combos(partition)
            present_set = list_combo_files(part_dir)
            if expected == len(present_set):
                continue
            expected_set = set(enumerate_combos(partition))
            missing = sorted(expected_set - present_set)
            extra = sorted(present_set - expected_set)
            if missing or extra:
                print(f"\n{part_str}  expected={expected} present={len(present_set)}")
                if missing:
                    print(f"  MISSING ({len(missing)}):")
                    for m in missing[:args.max_list]:
                        print(f"    {m}")
                    if len(missing) > args.max_list:
                        print(f"    ... +{len(missing) - args.max_list} more")
                if extra:
                    print(f"  UNEXPECTED on disk ({len(extra)}):")
                    for x in extra[:args.max_list]:
                        print(f"    {x}")


if __name__ == "__main__":
    main()
