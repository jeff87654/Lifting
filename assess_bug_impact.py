"""For the 4 anomalous combo files, check if their 'deduped' count
actually represents inflation (groups also appearing in other combo
files of the same partition), or truly new groups."""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

ANOMALOUS = [
    ("[4,4,4,4,2]", "[2,1]_[4,3]_[4,3]_[4,4]_[4,4].g"),
    ("[6,4,4,2,2]", "[2,1]_[2,1]_[4,3]_[4,4]_[6,3].g"),
    ("[4,4,3,3,2,2]", "[2,1]_[2,1]_[3,1]_[3,1]_[4,3]_[4,4].g"),
    ("[8,2,2,2,2,2]", "[2,1]_[2,1]_[2,1]_[2,1]_[2,1]_[8,23].g"),
]


def read_groups(fp):
    """Return set of group generator strings from a combo file."""
    try:
        with open(fp, 'r') as f:
            content = f.read()
    except Exception:
        return set()
    content = re.sub(r'\\\n', '', content)
    groups = set()
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            groups.add(line)
    return groups


for part, anom_name in ANOMALOUS:
    print(f"\n=== Partition {part} ===")
    part_dir = os.path.join(BASE, part)
    anom_fp = os.path.join(part_dir, anom_name)
    if not os.path.exists(anom_fp):
        print(f"  {anom_name} not found")
        continue
    anom_groups = read_groups(anom_fp)
    print(f"  Anomalous file: {anom_name}")
    print(f"    groups in file: {len(anom_groups):,}")
    other_groups = set()
    for fname in sorted(os.listdir(part_dir)):
        if fname == anom_name or not fname.endswith('.g') or 'backup' in fname:
            continue
        fp = os.path.join(part_dir, fname)
        other_groups |= read_groups(fp)
    overlap = anom_groups & other_groups
    unique_to_anom = anom_groups - other_groups
    print(f"    groups in other combo files: {len(other_groups):,}")
    print(f"    overlap (anom AND others): {len(overlap):,}")
    print(f"    unique to anom (true combo contribution): {len(unique_to_anom):,}")
    print(f"    INFLATION: {len(overlap):,} groups over-counted in this combo")
    total_partition_unique = len(anom_groups | other_groups)
    total_partition_claimed = len(anom_groups) + len(other_groups)
    print(f"    Partition total claimed: {total_partition_claimed:,}")
    print(f"    Partition actually distinct: {total_partition_unique:,}")
    print(f"    Over-count in partition total: {total_partition_claimed - total_partition_unique:,}")
