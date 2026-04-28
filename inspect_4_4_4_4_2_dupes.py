"""Investigate where the 137K additional duplicates in [4,4,4,4,2] come from."""
import os
import re
import collections

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[4,4,4,4,2]"

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

# For each group, which combo files contain it?
group_to_files = collections.defaultdict(list)
file_group_counts = {}

for fname in sorted(os.listdir(BASE)):
    if not fname.endswith('.g') or 'backup' in fname:
        continue
    fp = os.path.join(BASE, fname)
    gs = read_groups(fp)
    file_group_counts[fname] = len(gs)
    seen = set()
    for g in gs:
        if g not in seen:
            seen.add(g)
            group_to_files[g].append(fname)

# Summary
total_groups = len(group_to_files)
duplicated = {g: fs for g, fs in group_to_files.items() if len(fs) > 1}
print(f"Total distinct groups across partition: {total_groups:,}")
print(f"Groups appearing in >1 file: {len(duplicated):,}")
print()

# How many duplicates per file-pair
pair_counts = collections.Counter()
for fs in duplicated.values():
    for a in fs:
        for b in fs:
            if a < b:
                pair_counts[(a, b)] += 1

print("Top 10 file-pairs with most shared groups:")
for (a, b), cnt in pair_counts.most_common(10):
    print(f"  {cnt:>8,}  {a}  <->  {b}")
