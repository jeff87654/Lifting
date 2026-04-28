"""Identify all combos across parallel_s18 that match the S_n fast path
bug signature:

  - Partition has 3+ factors.
  - At least one factor is a natural S_n tag: (n, t_natural_S_n).
  - At least one OTHER factor is a non-natural S_n (same group, different
    action): matching known pairs.

We don't load groups; we match tag pairs using a lookup table of known
non-natural S_n actions by degree.
"""
import os, re
from collections import defaultdict

ROOT = r"C:\Users\jeffr\Downloads\Lifting"
CURRENT = os.path.join(ROOT, "parallel_s18")
PREBUG = os.path.join(ROOT, "parallel_s18_prebugfix_backup")

# Known natural S_n tags.
NATURAL_SN = {
    5: (5, 5),
    6: (6, 16),
    7: (7, 7),
    8: (8, 50),
    9: (9, 34),
    10: (10, 45),
    11: (11, 8),
    12: (12, 301),
    13: (13, 9),
    14: (14, 63),
    15: (15, 104),
    16: (16, 1954),
    17: (17, 10),
}

# Known non-natural transitive actions of S_m on d points.
# Derived from GAP's TransitiveGroups library. Only complete entries for S_5,
# S_6, S_7, S_8 up to degree 18.
#
# Format: NON_NATURAL_SN[d] = list of (d, t) tags where TG(d,t) is S_m for
# some m != d with m < d.
#
# S_5 (order 120, degree 5 natural):
#   - S_5 on 10 points (2-subsets): TG(10, ?)
#   - S_5 on 6 points: TG(6, ?)  (natural S_5 on {1..5} fixing one, i.e., not transitive)
#   - actually PGL(2,5) = S_5 on 6 points is transitive — TG(6, 11)?
#
# For our S18 scan, the relevant candidates are size <= 18.
# Data below is from GAP queries:

NON_NATURAL_SN_BY_ORDER = {
    # order 120 = |S_5|, on degrees > 5, t-numbers for TG
    120: [(6, 11), (10, 12), (10, 13), (12, 75), (15, 10), (15, 11)],
    # order 720 = |S_6|
    720: [(10, 32), (10, 34), (12, 268), (15, 14), (15, 18)],
    # order 5040 = |S_7|
    5040: [(14, 59), (14, 63), (15, 97), (15, 98), (15, 99)],
    # order 40320 = |S_8|
    40320: [(14, 62), (15, 104)],
}

ALL_NATURAL_SN_TAGS = set(NATURAL_SN.values())
ALL_NON_NATURAL_SN_BY_DEG = defaultdict(list)
for order, pairs in NON_NATURAL_SN_BY_ORDER.items():
    for d, t in pairs:
        # Figure out which n gives S_n with |S_n| = order
        n = {120: 5, 720: 6, 5040: 7, 40320: 8}[order]
        ALL_NON_NATURAL_SN_BY_DEG[d].append((d, t, n))  # degree d, t, S_n

def bug_signature(combo_filename):
    """Return (n, natural_tag, non_natural_tag) if combo matches the bug
    signature, else None."""
    tags_raw = re.findall(r"\[(\d+),(\d+)\]", combo_filename)
    tags = [(int(d), int(t)) for d, t in tags_raw]
    if len(tags) < 3:
        return None

    # Find natural S_n tags
    naturals = [(i, tag) for i, tag in enumerate(tags) if tag in ALL_NATURAL_SN_TAGS]
    if not naturals:
        return None

    # For each natural S_n, find another factor that's a non-natural iso
    for i, (nd, nt) in naturals:
        n = nd  # for natural S_n, the degree equals n
        for j, (d, t) in enumerate(tags):
            if j == i:
                continue
            # Check if (d, t) is a known non-natural S_n
            candidates = ALL_NON_NATURAL_SN_BY_DEG.get(d, [])
            for (cd, ct, cn) in candidates:
                if ct == t and cn == n:
                    return (n, (nd, nt), (d, t))
    return None

def parse_count(path):
    try:
        with open(path, "r") as f:
            head = f.read(500)
        m = re.search(r"^#\s*deduped:\s*(\d+)", head, flags=re.MULTILINE)
        if m:
            return int(m.group(1))
    except FileNotFoundError:
        return None
    return None

# Scan all combos in prebugfix (ground truth set).
print("Scanning combos for S_n fast path bug signature...")
print()

affected_combos = []
for part_dir in sorted(os.listdir(PREBUG)):
    prebug_part = os.path.join(PREBUG, part_dir)
    current_part = os.path.join(CURRENT, part_dir)
    if not os.path.isdir(prebug_part):
        continue
    for combo_file in os.listdir(prebug_part):
        if not combo_file.endswith(".g"):
            continue
        sig = bug_signature(combo_file)
        if sig is None:
            continue
        n, natural_tag, other_tag = sig
        pre = parse_count(os.path.join(prebug_part, combo_file))
        cur = parse_count(os.path.join(current_part, combo_file))
        affected_combos.append((part_dir, combo_file, pre, cur, n, natural_tag, other_tag))

print(f"Combos matching bug signature: {len(affected_combos)}")
print()

# Summary by regression status
regressed = [c for c in affected_combos if c[3] is not None and c[3] < c[2]]
same = [c for c in affected_combos if c[3] is not None and c[3] == c[2]]
bigger = [c for c in affected_combos if c[3] is not None and c[3] > c[2]]
pending = [c for c in affected_combos if c[3] is None]

print(f"  Regressed (current < prebug): {len(regressed)}, -{sum(c[2]-c[3] for c in regressed)} classes")
print(f"  Same:                         {len(same)}")
print(f"  Bigger (current > prebug):    {len(bigger)}")
print(f"  Pending (no current file):    {len(pending)}")
print()

print("Regressed combos:")
for c in regressed:
    print(f"  {c[0]}/{c[1]}: {c[2]} -> {c[3]} (n={c[4]}, natural={c[5]}, other={c[6]})")
print()

print("Pending combos (at risk — no current result yet):")
for c in pending[:20]:
    print(f"  {c[0]}/{c[1]}: prebug={c[2]}, n={c[4]}")
if len(pending) > 20:
    print(f"  ... and {len(pending) - 20} more")
print()

print("Same-count combos (suspect: bug may have silently dropped some, then")
print("the lost classes may coincidentally not exist for this combo):")
for c in same[:10]:
    print(f"  {c[0]}/{c[1]}: prebug={c[2]}, n={c[4]}")
if len(same) > 10:
    print(f"  ... and {len(same) - 10} more")

# Partition-level summary
print()
partitions_affected = defaultdict(int)
for c in affected_combos:
    partitions_affected[c[0]] += 1
print(f"Partitions affected: {len(partitions_affected)}")
for part, count in sorted(partitions_affected.items(), key=lambda x: -x[1])[:15]:
    print(f"  {part}: {count} combos")
