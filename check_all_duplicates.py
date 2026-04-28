"""Check each partition's total (sum of combo .g files) vs distinct-group count.
Reveals whether there are duplicate groups beyond the 4 known anomalies."""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"


def read_groups(fp):
    try:
        with open(fp, 'r') as f:
            content = f.read()
    except Exception:
        return []
    content = re.sub(r'\\\n', '', content)
    out = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            out.append(line)
    return out


partitions = []
for name in sorted(os.listdir(BASE)):
    if not (name.startswith('[') and name.endswith(']')):
        continue
    if os.path.isdir(os.path.join(BASE, name)):
        partitions.append(name)

print(f"{'Partition':<22} {'Raw sum':>12} {'Distinct':>12} {'Dupes':>10}")
print("-" * 62)
total_raw = 0
total_dist = 0
for p in partitions:
    part_dir = os.path.join(BASE, p)
    all_groups = []
    distinct = set()
    for fname in sorted(os.listdir(part_dir)):
        if not fname.endswith('.g') or 'backup' in fname:
            continue
        g = read_groups(os.path.join(part_dir, fname))
        all_groups.extend(g)
        distinct.update(g)
    raw = len(all_groups)
    dist = len(distinct)
    total_raw += raw
    total_dist += dist
    if raw != dist:
        print(f"{p:<22} {raw:>12,} {dist:>12,} {raw - dist:>10,}")

print("-" * 62)
print(f"{'TOTAL (all parts)':<22} {total_raw:>12,} {total_dist:>12,} {total_raw - total_dist:>10,}")
print()
print(f"Distinct FPF groups across all partitions (assumes 0 cross-partition dupes): {total_dist:,}")
print(f"Inherited from S17: 1,466,358")
print(f"Revised S18 total estimate: {total_dist + 1_466_358:,}")
