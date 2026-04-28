"""For Sn^2 combos where current == prebugfix, check whether the file
was rewritten or is stale. Use mtime comparison."""
from pathlib import Path
import re
from collections import Counter, defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
PRE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_prebugfix_backup")

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

def parse_factors(name):
    return [(int(d), int(k)) for d, k in re.findall(r"\[(\d+),(\d+)\]", name)]

def sn_factor_count(factors):
    """Count of S_n appearances per n>=5."""
    c = Counter()
    for d, k in factors:
        if d in SN_INDEX and k == SN_INDEX[d] and d >= 5:
            c[d] += 1
    return c

# Find prebugfix snapshot time (oldest mtime in prebugfix backup)
import os
pre_mtimes = []
for pdir in PRE.iterdir():
    if not pdir.is_dir(): continue
    for f in pdir.glob("*.g"):
        pre_mtimes.append(f.stat().st_mtime)
PRE_TIME = max(pre_mtimes) if pre_mtimes else 0
import datetime
print(f"Prebugfix backup latest mtime: {datetime.datetime.fromtimestamp(PRE_TIME)}")
print()

# For each Sn^2+ combo, find pre vs cur counts and mtime of cur file
records = []
for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    for cf in pdir.glob("*.g"):
        factors = parse_factors(cf.name)
        snc = sn_factor_count(factors)
        max_sn = max(snc.values()) if snc else 0
        if max_sn < 2: continue

        cc = deduped(cf)
        pf = PRE / pdir.name / cf.name
        pc = deduped(pf)
        cur_mtime = cf.stat().st_mtime
        records.append((pdir.name, cf.name, pc, cc, cur_mtime,
                        max_sn, dict(snc)))

# Categorize: stale = same count AND cur_mtime <= PRE_TIME
stale = []
fresh_same = []
fresh_diff = []
for r in records:
    pname, cname, pc, cc, cmtime, ms, snd = r
    if pc is None:
        continue  # skipped earlier
    if cc != pc:
        fresh_diff.append(r)
    elif cmtime > PRE_TIME + 1:
        fresh_same.append(r)
    else:
        stale.append(r)

print(f"Total Sn^>=2 combos: {len(records)}")
print(f"  cur != pre (changed):       {len(fresh_diff)}")
print(f"  cur == pre, file rewritten: {len(fresh_same)}  (verified: bug didn't apply)")
print(f"  cur == pre, STALE FILE:     {len(stale)}  (need rerun)")
print()

print("STALE Sn^2+ combos (sorted by current count, biggest first):")
stale.sort(key=lambda r: -(r[3] or 0))
for pname, cname, pc, cc, cmtime, ms, snd in stale[:30]:
    age_days = (PRE_TIME - cmtime) / 86400
    print(f"  {pname}/{cname}: count={cc} Sn^{ms}={snd} (mtime: {age_days:+.1f}d before backup)")

# Sum stale current counts to estimate what could improve
stale_total = sum(r[3] or 0 for r in stale)
print(f"\nSum of stale Sn^2+ current counts: {stale_total:,}")
print(f"(If each undercounts ~20%, expected gain: ~{int(stale_total * 0.2):,})")
