"""Analyze the partial TF-top catalog from dry_run_tops.py."""
import json
from collections import Counter

CATALOG = r"C:/Users/jeffr/Downloads/Lifting/tf_top_catalog_s16_s18.jsonl"

records = []
with open(CATALOG) as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

print(f"Total records: {len(records)}")

# By degree
by_n = Counter(r['n'] for r in records)
for n, c in sorted(by_n.items()):
    print(f"  n={n}: {c} combos")

# Unique (key, sig) pairs
unique = set((r['key'], r['sig']) for r in records)
print(f"\nUnique (key, sig) pairs: {len(unique)}")

# Unique keys (abstract groups)
unique_keys = Counter(r['key'] for r in records)
print(f"Unique abstract keys: {len(unique_keys)}")

# Q-size distribution among non-trivial
nontriv = [r for r in records if r['size_Q'] > 1]
print(f"\nNon-trivial Q (size > 1): {len(nontriv)} combos / "
      f"{len(set((r['key'], r['sig']) for r in nontriv))} unique (key,sig)")

if nontriv:
    sizes = sorted(r['size_Q'] for r in nontriv)
    print(f"|Q| buckets among non-trivial:")
    buckets = [100, 1000, 10000, 100000, 1000000, 10000000, 10**9, 10**12, 10**15]
    prev = 1
    for b in buckets:
        cnt = sum(1 for s in sizes if prev < s <= b)
        if cnt:
            print(f"  {prev:>12,} < |Q| <= {b:>14,} : {cnt:>5} combos")
        prev = b

# Top-10 most common (key, sig) pairs
print(f"\nTop 10 most-reused (key, sig):")
pair_counts = Counter((r['key'], r['sig']) for r in records if r['size_Q'] > 1)
for (k, sig), c in pair_counts.most_common(10):
    k_short = k if len(k) <= 60 else k[:60] + "..."
    print(f"  {c:>4} : {k_short} [{sig}]")
