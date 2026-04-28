"""diff_v2_topt.py — count-only diff scan between parallel_sn_v2 and parallel_sn_topt.

Usage: python diff_v2_topt.py <n>
"""
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
N = int(sys.argv[1])
V2 = ROOT / "parallel_sn_v2" / str(N)
TT = ROOT / "parallel_sn_topt" / str(N)

def deduped(p):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^# deduped:\s*(\d+)\s*$", txt, re.MULTILINE)
    return int(m.group(1)) if m else None

mismatches = []
totalv2 = totaltopt = 0
for part_dir in sorted(V2.iterdir()):
    if not part_dir.is_dir(): continue
    for v2f in sorted(part_dir.glob("*.g")):
        ttf = TT / part_dir.name / v2f.name
        v2c = deduped(v2f)
        ttc = deduped(ttf) if ttf.exists() else None
        if v2c is None: continue
        totalv2 += v2c
        if ttc is None:
            mismatches.append(f"{N}/{part_dir.name}/{v2f.stem}: v2={v2c} topt=MISSING")
            continue
        totaltopt += ttc
        if v2c != ttc:
            d = ttc - v2c
            mismatches.append(f"{N}/{part_dir.name}/{v2f.stem}: v2={v2c} topt={ttc} diff={d:+d}")

print(f"v2 total = {totalv2}")
print(f"topt total = {totaltopt}")
print(f"diff = {totaltopt - totalv2:+d}")
print(f"mismatches: {len(mismatches)}")
for m in mismatches:
    print(m)
