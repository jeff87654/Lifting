"""Compare ALL current parallel_s18 combos vs prebugfix_backup.
Find any combo where counts differ - tells us exactly which combos
have been recomputed and what the deltas are."""
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup")


def deduped(p):
    if not p.is_file():
        return None
    try:
        with open(p, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    return int(line.split(":", 1)[1].strip())
                if line.startswith("["):
                    return None
    except OSError:
        return None
    return None


total_cur = 0
total_pre = 0
matched = 0
mismatched = 0
only_cur = 0
only_pre = 0
mismatches = []  # (partition, combo, pre, cur)

for pdir in PRE.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["):
        continue
    cur_pdir = CUR / pdir.name
    for bf in pdir.glob("*.g"):
        pc = deduped(bf)
        if pc is None: continue
        cf = cur_pdir / bf.name
        cc = deduped(cf)
        if cc is None:
            only_pre += 1
            total_pre += pc
            continue
        total_cur += cc
        total_pre += pc
        if cc == pc:
            matched += 1
        else:
            mismatched += 1
            mismatches.append((pdir.name, bf.name, pc, cc))

# Files only in current (not in prebugfix)
for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["):
        continue
    pre_pdir = PRE / pdir.name
    for cf in pdir.glob("*.g"):
        if not (pre_pdir / cf.name).is_file():
            cc = deduped(cf)
            if cc is not None:
                only_cur += 1
                total_cur += cc

print(f"Matched (same count):     {matched:>8}")
print(f"Mismatched:               {mismatched:>8}")
print(f"Only in prebugfix:        {only_pre:>8}")
print(f"Only in current:          {only_cur:>8}")
print()
print(f"Total cur (matched+only): {total_cur:>10,}")
print(f"Total pre (matched+only): {total_pre:>10,}")
print()

if mismatches:
    inc = sorted([m for m in mismatches if m[3] > m[2]], key=lambda x: -(x[3]-x[2]))
    dec = sorted([m for m in mismatches if m[3] < m[2]], key=lambda x: -(x[2]-x[3]))
    print(f"Increases: {len(inc)}, total delta +{sum(m[3]-m[2] for m in inc):,}")
    print(f"Decreases: {len(dec)}, total delta -{sum(m[2]-m[3] for m in dec):,}")
    print()
    if inc:
        print("Top 30 INCREASES (cur > pre):")
        for p, c, pc, cc in inc[:30]:
            print(f"  {p}/{c}: {pc} -> {cc}  (+{cc-pc})")
    if dec:
        print()
        print("Top 30 DECREASES (cur < pre):")
        for p, c, pc, cc in dec[:30]:
            print(f"  {p}/{c}: {pc} -> {cc}  (-{pc-cc})")
