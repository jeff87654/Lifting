"""Identify combos affected by the unique-centralizer-complement bug.

The bug fires when the lifting algorithm hits a chief layer with a non-abelian
simple chief factor AND the centralizer happens to have size = idx. This
happens when a combo contains at least one NON-SOLVABLE transitive group
factor (whose composition series includes a non-abelian simple factor).

List combos where at least one factor (d, t) has t in the non-solvable
TI set for degree d.
"""
import os
import re
from collections import defaultdict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

# Non-solvable TIs per degree (from GAP)
NONSOLVABLE = {
    2: [], 3: [], 4: [],
    5: [4, 5],
    6: [12, 14, 15, 16],
    7: [5, 6, 7],
    8: [37, 43, 48, 49, 50],
    9: [27, 32, 33, 34],
    10: [7, 11, 12, 13, 22, 26, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42,
         43, 44, 45],
    11: [5, 6, 7, 8],
    12: [33, 74, 75, 76, 123, 124, 179, 180, 181, 182, 183, 218, 219, 220, 230,
         255, 256, 257, 269, 270, 272, 277, 278, 279, 285, 286, 287, 288, 293,
         295, 296, 297, 298, 299, 300, 301],
    13: [7, 8, 9],
    14: [10, 16, 17, 19, 30, 33, 34, 39, 42, 43, 46, 47, 49, 50, 51, 52, 53,
         54, 55, 56, 57, 58, 59, 60, 61, 62, 63],
    15: [5, 10, 15, 16, 20, 21, 22, 23, 24, 28, 29, 47, 53, 61, 62, 63, 69, 70,
         72, 76, 77, 78, 83, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99,
         100, 101, 102, 103, 104],
    16: [713, 714, 715, 1035, 1036, 1080, 1081, 1328, 1329, 1504, 1505, 1506,
         1507, 1508, 1653, 1654, 1753, 1801, 1802, 1803, 1804, 1805, 1838,
         1839, 1840, 1842, 1843, 1844, 1861, 1873, 1878, 1882, 1883, 1902,
         1903, 1906, 1916, 1938, 1940, 1944, 1945, 1946, 1948, 1949, 1950,
         1951, 1952, 1953, 1954],
    17: [6, 7, 8, 9, 10],
    18: [90, 144, 145, 146, 227, 260, 261, 262, 362, 363, 364, 365, 377, 427,
         452, 468, 596, 664, 665, 666, 722, 723, 736, 787, 788, 789, 790, 791,
         802, 845, 846, 847, 848, 849, 855, 856, 886, 887, 888, 890, 897, 898,
         899, 900, 911, 913, 914, 925, 933, 934, 935, 936, 937, 938, 946, 947,
         948, 949, 950, 952, 953, 954, 955, 956, 957, 958, 959, 960, 961, 962,
         963, 964, 965, 966, 967, 968, 969, 970, 971, 972, 973, 974, 975, 976,
         977, 978, 979, 980, 981, 982, 983],
}
NONSOLVABLE_SET = {d: set(ts) for d, ts in NONSOLVABLE.items()}


def parse_combo(name):
    name = name.replace(".g", "")
    return [(int(d), int(t)) for d, t in re.findall(r"\[(\d+),(\d+)\]", name)]


def has_nonsolvable(factors):
    return any(t in NONSOLVABLE_SET.get(d, set()) for d, t in factors)


def dedup(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        return None
    return None


affected_by_partition = defaultdict(list)  # part -> list of (name, count)
total_affected_groups = 0
total_affected_combos = 0
total_combos = 0
total_partitions_affected = set()

for p in sorted(os.listdir(BASE)):
    full = os.path.join(BASE, p)
    if not os.path.isdir(full) or "bogus" in p or not p.startswith("["):
        continue
    for f in sorted(os.listdir(full)):
        if not f.endswith(".g") or "corrupted" in f:
            continue
        factors = parse_combo(f)
        if not factors:
            continue
        total_combos += 1
        if has_nonsolvable(factors):
            n = dedup(os.path.join(full, f)) or 0
            affected_by_partition[p].append((f, n))
            total_affected_groups += n
            total_affected_combos += 1
            total_partitions_affected.add(p)

# Summarize
print(f"Total combos scanned:      {total_combos}")
print(f"Affected combos:           {total_affected_combos}  "
      f"({100.0*total_affected_combos/max(1,total_combos):.1f}%)")
print(f"Partitions with any affected combo: {len(total_partitions_affected)}")
print(f"Total groups in affected combos:    {total_affected_groups:,}")
print()
print("Per-partition breakdown (top by affected-combo count):")
rows = sorted(affected_by_partition.items(),
              key=lambda kv: -len(kv[1]))
print(f"{'partition':<28} {'# affected':>10} {'sum deduped':>14}")
print("-" * 60)
for p, entries in rows:
    total = sum(n for _, n in entries)
    print(f"{p:<28} {len(entries):>10} {total:>14,}")

# Write a manifest file listing every affected combo
out = r"C:\Users\jeffr\Downloads\Lifting\affected_combos.txt"
with open(out, "w") as fh:
    fh.write("# Combos affected by the unique-centralizer-complement bug\n")
    fh.write("# Format: partition\tcombo_file\tcurrent_deduped\n")
    for p in sorted(affected_by_partition):
        for f, n in sorted(affected_by_partition[p]):
            fh.write(f"{p}\t{f}\t{n}\n")
print(f"\nWrote full manifest to: {out}")
