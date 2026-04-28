"""Count groups in each partition's combo .g files, properly handling
multi-line group representations (GAP uses backslash-newline continuation)."""
import os
import glob
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

def count_groups_in_file(fp):
    """Count group records in a GAP .g file. Groups start with `[` or `Group(`
    and span multiple lines via backslash-newline continuation."""
    try:
        with open(fp, 'r') as f:
            content = f.read()
    except Exception:
        return 0
    # Strip line continuations so each logical group is on one line
    content = re.sub(r'\\\n', '', content)
    count = 0
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # group representations start with '[' (lists of gens) or 'Group(' etc.
        if line.startswith('[') or line.startswith('Group('):
            count += 1
    return count

def count_partition(part_dir):
    total = 0
    combo_count = 0
    try:
        names = sorted(os.listdir(part_dir))
    except FileNotFoundError:
        return 0, 0
    for name in names:
        if not name.endswith('.g'):
            continue
        if 'backup' in name:
            continue
        fp = os.path.join(part_dir, name)
        n = count_groups_in_file(fp)
        total += n
        combo_count += 1
    return total, combo_count

# Enumerate partition directories (brackets in name)
partitions = []
for name in os.listdir(BASE):
    full = os.path.join(BASE, name)
    if os.path.isdir(full) and name.startswith('[') and name.endswith(']'):
        partitions.append(name)

partitions.sort()

rows = []
for p in partitions:
    total, combos = count_partition(os.path.join(BASE, p))
    rows.append((p, total, combos))

# Sort by count descending
rows.sort(key=lambda r: -r[1])

grand_total = sum(r[1] for r in rows)
grand_combos = sum(r[2] for r in rows)
nonzero = [r for r in rows if r[1] > 0]

print(f"{'Partition':<25} {'Groups':>12} {'Combos':>8}")
print("-" * 50)
for p, n, c in rows:
    print(f"{p:<25} {n:>12,} {c:>8}")
print("-" * 50)
print(f"{'TOTAL':<25} {grand_total:>12,} {grand_combos:>8}")
print()
print(f"Partitions with output: {len(nonzero)} / {len(rows)}")
print(f"FPF total so far: {grand_total:,}")
print(f"Inherited from S17: 1,466,358")
print(f"Running S18 estimate: {grand_total + 1_466_358:,}")
