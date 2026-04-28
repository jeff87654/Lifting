"""Identify combos in current that are IDENTICAL to bugfix1 backup and involve
S_n >= 5 factors (the ones most affected by the bugs we fixed).

If a combo is same in both, it was NOT rerun after the bug fixes — so if
the old code had a bug on that combo, the undercount persists.
"""
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_bugfix1_backup")

# S_n >= 5 transitive groups (symmetric groups acting naturally)
SN_INDICES = {
    5: [5],        # T(5,5) = S_5
    6: [16],       # T(6,16) = S_6
    7: [7],        # T(7,7) = S_7
    8: [50],       # T(8,50) = S_8
    9: [34],       # T(9,34) = S_9 (if exists)
    10: [45],      # T(10,45) = S_10
}


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


def combo_has_sn(cname):
    """Check if combo file name has an S_n factor."""
    import re
    pairs = re.findall(r"\[(\d+),(\d+)\]", cname)
    for d, i in pairs:
        d, i = int(d), int(i)
        if d in SN_INDICES and i in SN_INDICES[d]:
            return True, d
    return False, None


def load_tree(root):
    out = {}
    for pdir in root.iterdir():
        if not pdir.is_dir() or not pdir.name.startswith("["):
            continue
        for cf in pdir.glob("*.g"):
            d = deduped(cf)
            if d is not None:
                out[(pdir.name, cf.name)] = d
    return out


print("Loading trees...")
current = load_tree(CUR)
backup = load_tree(BK)

common = set(current) & set(backup)
print(f"Common: {len(common)} combo files")

# Find combos with S_n factor where current == backup (never rerun)
stale_by_size = defaultdict(lambda: {'count': 0, 'total': 0, 'examples': []})

for key in common:
    part, cname = key
    if current[key] != backup[key]:
        continue  # was rerun (or bug on one side) - skip
    has_sn, n = combo_has_sn(cname)
    if not has_sn: continue
    stale_by_size[n]['count'] += 1
    stale_by_size[n]['total'] += current[key]
    if len(stale_by_size[n]['examples']) < 3:
        stale_by_size[n]['examples'].append((part, cname, current[key]))

print()
print(f"{'Sn':>6} {'# combos':>10} {'sum':>12}  examples")
print("-" * 75)
total_count = 0
total_sum = 0
for n in sorted(stale_by_size):
    s = stale_by_size[n]
    ex = s['examples'][0]
    print(f"S_{n:<4} {s['count']:>10} {s['total']:>12,}  {ex[0]}/{ex[1]}: {ex[2]}")
    total_count += s['count']
    total_sum += s['total']
print()
print(f"Total 'stale S_n combos (same as bugfix1 backup)': {total_count} combos, "
      f"{total_sum:,} classes attributed to them")
print()
print("If ~20% of these are undercounting by ~20% (as observed increases suggest),")
print(f"potential hidden undercount: {int(total_sum * 0.04):,} classes")
