"""Compare [6,4,4,4] combo counts across:
  - current parallel_s18/[6,4,4,4]/
  - parallel_s18_prebugfix_backup/[6,4,4,4]/
  - parallel_s18_bugfix1_backup/[6,4,4,4]/

Identify patterns: which combos increased on rerun, decreased, stayed same,
or exist only in backups.
"""
from pathlib import Path
from collections import Counter

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup/[6,4,4,4]")
BUG1 = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_bugfix1_backup/[6,4,4,4]")


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


def load_dir(p):
    out = {}
    if not p.is_dir(): return out
    for cf in p.glob("*.g"):
        d = deduped(cf)
        if d is not None:
            out[cf.name] = d
    return out


cur = load_dir(CUR)
pre = load_dir(PRE)
bug1 = load_dir(BUG1)

print(f"current:  {len(cur)} combos, total {sum(cur.values()):,}")
print(f"prebugfix: {len(pre)} combos, total {sum(pre.values()):,}")
print(f"bugfix1:   {len(bug1)} combos, total {sum(bug1.values()):,}")
print()

# Compare current to each backup
def compare(current, backup, name):
    common = set(current) & set(backup)
    only_cur = set(current) - set(backup)
    only_bk = set(backup) - set(current)
    increased = []
    decreased = []
    same = 0
    for k in common:
        if current[k] > backup[k]:
            increased.append((k, backup[k], current[k], current[k] - backup[k]))
        elif current[k] < backup[k]:
            decreased.append((k, backup[k], current[k], backup[k] - current[k]))
        else:
            same += 1
    increased.sort(key=lambda x: -x[3])
    decreased.sort(key=lambda x: -x[3])
    print(f"=== current vs {name} ===")
    print(f"  common: {len(common)}, same: {same}, increased: {len(increased)}, decreased: {len(decreased)}")
    print(f"  only in current: {len(only_cur)}, only in {name}: {len(only_bk)}")
    print(f"  delta from increases: +{sum(x[3] for x in increased)}")
    print(f"  delta from decreases: -{sum(x[3] for x in decreased)}")
    print(f"  total in only-{name}: {sum(backup[k] for k in only_bk):,}")
    if increased:
        print(f"  top 5 increases:")
        for k, b, c, d in increased[:5]:
            print(f"    {k}: {b} -> {c}  (+{d})")
    if decreased:
        print(f"  top 5 decreases:")
        for k, b, c, d in decreased[:5]:
            print(f"    {k}: {b} -> {c}  (-{d})")
    if only_bk:
        items = sorted(only_bk, key=lambda k: -backup[k])
        print(f"  top 5 only in {name}:")
        for k in items[:5]:
            print(f"    {k}: {backup[k]}")
    print()

compare(cur, pre, "prebugfix")
compare(cur, bug1, "bugfix1")
