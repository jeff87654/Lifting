"""Find all combos with 2+ identical NON-SOLVABLE T(d,k) factors.
Compare current vs prebugfix backup to find STALE combos."""
from pathlib import Path
import re
from collections import Counter

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup")

# Non-solvable T(d,k) for d=5..9 (relevant for squaring in S_18)
NONSOLV = {
    5: {4, 5},
    6: {12, 14, 15, 16},
    7: {5, 6, 7},
    8: {37, 43, 48, 49, 50},
    9: {27, 32, 33, 34},
}

def deduped(p):
    if not p.is_file(): return None
    try:
        with open(p, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    return int(line.split(":",1)[1].strip())
                if line.startswith("["): return None
    except OSError: return None
    return None

def parse_factors(name):
    return [(int(d), int(k)) for d, k in re.findall(r"\[(\d+),(\d+)\]", name)]


# Find prebugfix snapshot latest mtime
import os
PRE_TIME = max((f.stat().st_mtime for pdir in PRE.iterdir() if pdir.is_dir()
                for f in pdir.glob("*.g")), default=0)


# Categorize all combos
records = []
for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    for cf in pdir.glob("*.g"):
        factors = parse_factors(cf.name)
        # Count occurrences of each non-solvable (d,k) pair
        c = Counter()
        for d, k in factors:
            if d in NONSOLV and k in NONSOLV[d]:
                c[(d, k)] += 1
        max_pair = max(c.values()) if c else 0
        if max_pair < 2: continue

        cc = deduped(cf)
        pf = PRE / pdir.name / cf.name
        pc = deduped(pf)
        cmtime = cf.stat().st_mtime
        records.append((pdir.name, cf.name, pc, cc, cmtime, max_pair, dict(c)))


# Categorize
in_pre = [r for r in records if r[2] is not None]
no_pre = [r for r in records if r[2] is None]
fresh_diff = [r for r in in_pre if r[3] != r[2]]
fresh_same = [r for r in in_pre if r[3] == r[2] and r[4] > PRE_TIME + 1]
stale_same = [r for r in in_pre if r[3] == r[2] and r[4] <= PRE_TIME + 1]

print(f"Total combos with 2+ identical non-solvable factors: {len(records)}")
print(f"  in prebugfix backup:    {len(in_pre)}")
print(f"    cur != pre (rerun changed): {len(fresh_diff)}  delta_sum = {sum(r[3]-r[2] for r in fresh_diff):+,}")
print(f"    cur == pre, file fresh:     {len(fresh_same)}  (verified, same)")
print(f"    cur == pre, STALE:          {len(stale_same)}  (need rerun)")
print(f"  NOT in prebugfix:       {len(no_pre)}  (no backup, can rerun to compare)")
print()

# Show no-prebugfix combos by structure type
if no_pre:
    print(f"Top 30 'no prebugfix' combos (by current count):")
    no_pre.sort(key=lambda r: -(r[3] or 0))
    for pname, cname, _, cc, _, mp, cmap in no_pre[:30]:
        # Pretty print Sn^k notation
        nonsolv_str = ", ".join(f"T({d},{k})^{c}" for (d,k), c in cmap.items() if c >= 2)
        print(f"  {pname}/{cname}: {cc}  -- {nonsolv_str}")
    print(f"\n  Sum of no-prebugfix counts: {sum(r[3] or 0 for r in no_pre):,}")
