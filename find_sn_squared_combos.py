"""Find all combos containing 2+ copies of any S_n (n>=5).
For each, compare current disk count vs prebugfix backup.
Mark NEVER_COMPARED when no prebugfix backup exists (= never reverified).
"""
from pathlib import Path
import re
from collections import Counter, defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup")

# S_n = T(d, k_max). NrTransitiveGroups for n=5..14.
SN_INDEX = {5: 5, 6: 16, 7: 7, 8: 50, 9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63}

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


def parse_combo_filename(name):
    """Return list of (d, k) from a filename like '[2,1]_[4,3]_[5,5].g'."""
    parts = re.findall(r"\[(\d+),(\d+)\]", name)
    return [(int(d), int(k)) for d, k in parts]


# Categorize all current combos
def is_sn_pair(factors):
    """Return list of n where Sn appears 2+ times in factors."""
    counts = Counter()
    for d, k in factors:
        if d in SN_INDEX and k == SN_INDEX[d] and d >= 5:
            counts[d] += 1
    return [n for n, c in counts.items() if c >= 2]


same_count = 0
diff_count = 0
no_prebugfix = 0
no_disk = 0
diffs = []
no_backup_combos = defaultdict(list)

for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    for cf in pdir.glob("*.g"):
        factors = parse_combo_filename(cf.name)
        sn_pairs = is_sn_pair(factors)
        if not sn_pairs: continue

        cc = deduped(cf)
        if cc is None:
            no_disk += 1
            continue

        pf = PRE / pdir.name / cf.name
        pc = deduped(pf)
        if pc is None:
            no_prebugfix += 1
            no_backup_combos[pdir.name].append((cf.name, sn_pairs, cc))
            continue

        if cc == pc:
            same_count += 1
        else:
            diff_count += 1
            diffs.append((pdir.name, cf.name, pc, cc, sn_pairs))


total = same_count + diff_count + no_prebugfix
print(f"Total Sn^2 combos in current: {total}")
print(f"  same as prebugfix:    {same_count}")
print(f"  differ from prebugfix:{diff_count}  (sum delta: {sum(c-p for _,_,p,c,_ in diffs):+,})")
print(f"  NO prebugfix backup:  {no_prebugfix}  (UNVERIFIED)")
print()

if diffs:
    diffs.sort(key=lambda x: -(x[3]-x[2]))
    print("Top differs (verified the bug fix moved them up):")
    for p, c, pc, cc, sn in diffs[:15]:
        print(f"  {p}/{c}: {pc} -> {cc}  (+{cc-pc})  Sn^2: {sn}")
    print()

# Show partitions with most unverified Sn^2 combos
print("Partitions with UNVERIFIED Sn^2 combos (no prebugfix):")
unv = sorted(no_backup_combos.items(), key=lambda x: -len(x[1]))
for pname, lst in unv[:20]:
    sn_dist = Counter()
    for n, sn, cc in lst:
        for s in sn: sn_dist[s] += 1
    sum_cc = sum(cc for _, _, cc in lst)
    print(f"  {pname:<22} {len(lst):>4} unverified combos, sum={sum_cc:>8,}, Sn^2: {dict(sn_dist)}")
