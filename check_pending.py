"""For each S18 partition, compute expected combo count (non-decreasing TI
across equal-size blocks) and compare to actual combo files in the folder.
Report partitions with missing combos."""
import os
import re
import subprocess
from math import comb

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

# NrTransitiveGroups(d) for d = 2..18. Fixed GAP-library values.
NR_TG = {
    2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63,
    15: 104, 16: 1954, 17: 10, 18: 983,
}


def expected_combos(partition):
    """Number of non-decreasing-TI orderings for sorted partition.

    Parts with the same degree are constrained to non-decreasing TI across
    adjacent positions (IterateCombinations rule). Groups of equal parts
    each contribute C(n+k-1, k) where n=NrTransitiveGroups(d), k=multiplicity.
    Distinct-degree blocks multiply.
    """
    counts = {}
    for d in partition:
        counts[d] = counts.get(d, 0) + 1
    total = 1
    for d, k in counts.items():
        total *= comb(NR_TG[d] + k - 1, k)
    return total


def parse_folder_name(name):
    # "[8,4,2,2,2]" -> (8,4,2,2,2)
    m = re.fullmatch(r"\[(\d+(?:,\d+)*)\]", name)
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split(","))


def main():
    rows = []
    for name in os.listdir(BASE):
        full = os.path.join(BASE, name)
        if not os.path.isdir(full):
            continue
        if "bogus" in name:
            continue
        part = parse_folder_name(name)
        if part is None:
            continue
        try:
            expected = expected_combos(part)
        except KeyError:
            continue
        actual = sum(1 for f in os.listdir(full) if f.endswith(".g"))
        rows.append((name, part, expected, actual))

    # Show pending (actual < expected)
    pending = [r for r in rows if r[3] < r[2]]
    pending.sort(key=lambda r: r[2] - r[3], reverse=True)
    print(f"Total partitions: {len(rows)}")
    print(f"Complete (actual >= expected): {len(rows) - len(pending)}")
    print(f"Pending (actual < expected):   {len(pending)}")
    print()
    if pending:
        print(f"{'partition':<30} {'combos':>10} {'expected':>10} {'missing':>10}")
        print("-" * 64)
        for name, _, exp, act in pending:
            print(f"{name:<30} {act:>10} {exp:>10} {exp-act:>10}")
    # Sanity-check: any over-count?
    over = [r for r in rows if r[3] > r[2]]
    if over:
        print("\nWARNING: over-count (actual > expected):")
        for name, _, exp, act in over:
            print(f"  {name}: {act} > {exp}")


if __name__ == "__main__":
    main()
