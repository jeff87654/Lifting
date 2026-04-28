"""Find combos that MAY still be undercounting:
  - Same partition + T(5,5)/T(5,5)×T(5,5) pattern as known increases
  - Currently on disk (so they were run) but not in backup (so they weren't rerun under new code)
  - Combo file never overwritten since backup

Strategy:
  1. For each partition with ANY increase, list combos in CURRENT that match the
     T(5,5) pattern (or the pattern that triggered bug).
  2. For each such combo, check if it's in backup (then we know it was reproduced)
     or if it predates the backup (then rerun happened) or is "only in current"
     (newer, assumed correct).
  3. Focus on combos matched between backup and current — if they're identical,
     they weren't rerun to benefit from the fix.
"""
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup")

# Partitions that had increases
AFFECTED_PARTITIONS = set()


def deduped(path):
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    try: return int(line.split(":",1)[1].strip())
                    except ValueError: return None
                if line.startswith("["):
                    return None
    except OSError:
        return None
    return None


# Load both trees per-partition
def load_tree(root):
    out = {}  # (partition, combo_file_name) -> count
    for pdir in root.iterdir():
        if not pdir.is_dir() or not pdir.name.startswith("["):
            continue
        for cf in pdir.glob("*.g"):
            d = deduped(cf)
            if d is not None:
                out[(pdir.name, cf.name)] = d
    return out


print("Loading current...")
current = load_tree(CUR)
print(f"  {len(current)} combo files")
print("Loading prebugfix backup...")
backup = load_tree(BK)
print(f"  {len(backup)} combo files")

# Common combos
common = set(current) & set(backup)
increases = []
for k in common:
    if current[k] > backup[k]:
        increases.append((k, backup[k], current[k], current[k] - backup[k]))

# Extract partitions with increases
affected_partitions = set(k[0][0] for k in increases)
print(f"\nAffected partitions: {sorted(affected_partitions)}")

# For each affected partition, list combos with T(5,5) × T(5,5) pattern
# that are STILL SAME in current and backup (potential undercounts)
# AND total deduped from those
print()
print(f"{'partition':22} {'still matched':>15} {'sum':>10}  suspects")
print("-" * 70)
total_suspect_sum = 0
for part in sorted(affected_partitions):
    # combos that have T(5,5) pattern
    suspect_combos = []
    for (p, cn), backup_count in backup.items():
        if p != part: continue
        if cn not in current: continue
        if "[5,5]" not in cn: continue  # rough pattern filter
        if current[(p, cn)] == backup_count:
            suspect_combos.append((cn, backup_count))
    if suspect_combos:
        ssum = sum(c for _, c in suspect_combos)
        total_suspect_sum += ssum
        # Also estimate how many are T(5,5)x2 patterns
        double_5_5 = [c for c in suspect_combos if cn.count("[5,5]") >= 2]
        print(f"{part:22} {len(suspect_combos):>15} {ssum:>10}")

print()
print(f"Total in SAME-as-backup T(5,5)-involving combos: {total_suspect_sum:,}")
print("(These may be undercounting by similar factor to observed increases)")
