"""Compare per-combo class counts between S_18 backups and current.

For each combo file that exists in BOTH backup and current:
  - parse # deduped
  - if current > backup: REDO found more classes (bug fix win)
  - if current < backup: REDO found fewer (suspicious)
  - if equal: same
Also list combo files in backup but missing from current (deleted as corrupt).
"""
import os, re, sys
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BACKUPS = [
    Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup"),
    Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_bugfix1_backup"),
]


def deduped(path):
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    try:
                        return int(line.split(":",1)[1].strip())
                    except ValueError:
                        return None
                if line.startswith("["):
                    return None  # past header without finding marker
    except OSError:
        pass
    return None


for backup in BACKUPS:
    if not backup.is_dir():
        continue
    print(f"\n=== {backup.name} ===")
    increases = defaultdict(list)  # partition -> [(combo, backup_count, current_count)]
    decreases = defaultdict(list)
    only_in_backup = defaultdict(list)  # partition -> [combos]
    total_backup = 0
    total_current_matched = 0
    num_matched = 0

    for pdir in sorted(backup.iterdir()):
        if not pdir.is_dir() or not pdir.name.startswith("["):
            continue
        cur_pdir = CUR / pdir.name
        for bf in pdir.glob("*.g"):
            bc = deduped(bf)
            if bc is None:
                continue
            total_backup += bc
            cf = cur_pdir / bf.name
            if cf.is_file():
                cc = deduped(cf)
                if cc is None:
                    continue
                num_matched += 1
                total_current_matched += cc
                if cc > bc:
                    increases[pdir.name].append((bf.name, bc, cc))
                elif cc < bc:
                    decreases[pdir.name].append((bf.name, bc, cc))
            else:
                only_in_backup[pdir.name].append((bf.name, bc))

    print(f"  matched combos: {num_matched}")
    print(f"  sum of deduped in backup (matched set): {total_backup - sum(bc for lst in only_in_backup.values() for _, bc in lst):,}")
    print(f"  sum of deduped in current (matched set): {total_current_matched:,}")

    delta_cur = total_current_matched - (total_backup - sum(bc for lst in only_in_backup.values() for _, bc in lst))
    print(f"  delta (current - backup, matched set): {delta_cur:+,}")
    print(f"  INCREASES: {sum(len(v) for v in increases.values())} combos across "
          f"{len([k for k,v in increases.items() if v])} partitions")
    if increases:
        # top 10 biggest increases
        flat = [(part, cname, bc, cc, cc-bc)
                for part, lst in increases.items() for cname, bc, cc in lst]
        flat.sort(key=lambda x: -x[4])
        print("  top 10 by delta:")
        for part, cn, bc, cc, d in flat[:10]:
            print(f"    {part}/{cn}: {bc} -> {cc}  (+{d})")
    print(f"  DECREASES: {sum(len(v) for v in decreases.values())} combos")
    if decreases:
        flat = [(part, cname, bc, cc, bc-cc)
                for part, lst in decreases.items() for cname, bc, cc in lst]
        flat.sort(key=lambda x: -x[4])
        print("  top 10 by drop (WATCH - should be zero if bugs were undercounts):")
        for part, cn, bc, cc, d in flat[:10]:
            print(f"    {part}/{cn}: {bc} -> {cc}  (-{d})")
    print(f"  ONLY IN BACKUP: {sum(len(v) for v in only_in_backup.values())} combos")
    if only_in_backup:
        flat = [(part, cn, bc)
                for part, lst in only_in_backup.items() for cn, bc in lst]
        flat.sort(key=lambda x: -x[2])
        print("  top 10 by size:")
        for part, cn, bc in flat[:10]:
            print(f"    {part}/{cn}: {bc}")
