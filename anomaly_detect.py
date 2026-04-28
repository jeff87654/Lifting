"""Flag combos with anomalously low counts given their transitive-group factors.

Strategy:
  - Group combos by "non-trivial signature" (factors ignoring [2,1]=C_2).
    E.g., [4,3]_[6,9] appears in ANY partition where the non-[2,1] factors
    are exactly ([4,3], [6,9]).
  - For each signature, collect counts across partitions.
  - Flag partitions where the count is far below the median for that
    signature family.
  - Secondary check: within each partition, rank per-[6,Y] or per-[8,Y]
    productivity and flag unusually low cells.
"""
import os
import re
from collections import defaultdict
from statistics import median

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"


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


def parse_combo_filename(name):
    """[2,1]_[2,1]_[4,3]_[6,9].g -> list of (d, t) tuples."""
    name = name.replace(".g", "")
    factors = re.findall(r"\[(\d+),(\d+)\]", name)
    return [(int(d), int(t)) for d, t in factors]


def non_trivial_signature(factors):
    """Drop all [2,1] factors to get the 'interesting' part."""
    return tuple(sorted(f for f in factors if f != (2, 1)))


# Load all combo data
all_combos = []  # list of (partition_name, sig, count, filename)
for p in os.listdir(BASE):
    full = os.path.join(BASE, p)
    if not os.path.isdir(full): continue
    if "bogus" in p: continue
    if not p.startswith("["): continue
    for f in os.listdir(full):
        if not f.endswith(".g") or "corrupted" in f: continue
        factors = parse_combo_filename(f)
        if not factors: continue
        n = dedup(os.path.join(full, f))
        if n is None: continue
        sig = non_trivial_signature(factors)
        all_combos.append((p, sig, n, f))

# Group by non-trivial signature
by_sig = defaultdict(list)  # sig -> [(partition, count, file), ...]
for p, sig, n, f in all_combos:
    by_sig[sig].append((p, n, f))

# For each signature appearing in >1 partitions, find outliers
anomalies = []
for sig, entries in by_sig.items():
    if len(entries) < 2: continue
    counts = [e[1] for e in entries]
    m = median(counts)
    if m == 0: continue
    for p, n, f in entries:
        # Flag as anomalous if count < 50% of median AND median is substantive
        if m >= 100 and n < 0.5 * m:
            ratio = n / m
            anomalies.append((sig, m, p, n, f, ratio))

print(f"Anomaly Report: combos with count < 50% of cross-partition median")
print(f"  (signatures with >1 partition, median >= 100)")
print()
print(f"{'partition':<22} {'non-triv sig':<35} {'this':>8} {'median':>8} {'ratio':>6}  {'file'}")
print("-" * 120)
anomalies.sort(key=lambda x: x[5])
for sig, m, p, n, f, ratio in anomalies[:40]:
    sig_str = ",".join(f"[{d},{t}]" for d,t in sig)
    print(f"{p:<22} {sig_str:<35} {n:>8,} {m:>8,} {ratio:>6.2%}  {f}")

print()
print(f"Total anomalies flagged: {len(anomalies)}")

# Also: per-partition, find combos that are outliers within the partition
# (compared to their sibling combos with same-but-one factor)
print()
print("=" * 120)
print("Per-partition within-family outliers (combo < 25% of median of same last-factor family)")
print()

# Group within each partition by "all but last factor"
by_partition_family = defaultdict(lambda: defaultdict(list))
for p, sig, n, f in all_combos:
    factors = parse_combo_filename(f)
    if len(factors) < 2: continue
    family_key = tuple(factors[:-1])  # all but last
    by_partition_family[p][family_key].append((factors[-1], n, f))

within_anomalies = []
for p, families in by_partition_family.items():
    for family_key, members in families.items():
        if len(members) < 5: continue
        counts = [m[1] for m in members]
        med = median(counts)
        if med < 100: continue
        for last, n, f in members:
            if n < 0.25 * med and med > 0:
                within_anomalies.append((p, family_key, last, n, med, f))

print(f"{'partition':<22} {'family':<45} {'last':<10} {'this':>8} {'fam-med':>8}  {'file'}")
print("-" * 120)
for p, fk, last, n, med, f in sorted(within_anomalies, key=lambda x: x[3]/x[4])[:30]:
    fk_str = ",".join(f"[{d},{t}]" for d,t in fk)
    last_str = f"[{last[0]},{last[1]}]"
    print(f"{p:<22} {fk_str:<45} {last_str:<10} {n:>8,} {med:>8,}  {f}")

print(f"\nTotal within-partition anomalies: {len(within_anomalies)}")
