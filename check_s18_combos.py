"""Inspect S_18 per-combo files: find partitions with missing combos."""
import os, re
from pathlib import Path
from math import comb

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")

# Transitive group counts for each degree
TG_COUNT = {2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
            9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63,
            15: 104, 16: 1954, 17: 10, 18: 983}

def expected_combos(partition):
    """Combos for partition: product over distinct block-size groups of
    multiset-of-factors over TG[size]."""
    from collections import Counter
    block_counts = Counter(partition)
    total = 1
    for size, mult in block_counts.items():
        n = TG_COUNT.get(size, None)
        if n is None: return None
        # Multisets of size mult from n options
        total *= comb(n + mult - 1, mult)
    return total

def parse_partition(s):
    """'[6,4,4,2,2]' -> [6,4,4,2,2]"""
    if not s.startswith('['): return None
    return [int(x) for x in s.strip('[]').split(',')]

results = []
for d in sorted(os.listdir(BASE)):
    if not d.startswith('['): continue
    dpath = BASE / d
    if not dpath.is_dir(): continue
    part = parse_partition(d)
    expected = expected_combos(part)
    combos = list(dpath.glob("*.g"))
    has_summary = (dpath / "summary.txt").is_file()
    actual = len(combos)
    missing = expected - actual if expected else None
    results.append((d, expected, actual, missing, has_summary))

# Report
print(f"{'partition':30} {'expected':>10} {'actual':>10} {'missing':>10} {'summary':>8}")
print("-" * 75)
pending_summary = []
missing_combos = []
for d, exp, act, miss, hs in results:
    flag = ""
    if not hs:
        flag += " NOSUM"
        pending_summary.append(d)
    if miss and miss > 0:
        flag += " MISS"
        missing_combos.append((d, miss))
    if flag:
        print(f"{d:30} {exp or '?':>10} {act:>10} {miss if miss else '':>10} {'yes' if hs else 'no':>8}  {flag}")

print()
print(f"No summary: {len(pending_summary)} partitions")
print(f"Missing combos: {len(missing_combos)} partitions")
if missing_combos:
    total_missing = sum(m for _, m in missing_combos)
    print(f"Total missing combo files: {total_missing}")
