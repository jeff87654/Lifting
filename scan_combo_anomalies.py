"""Scan all combo .g files for anomalies where # deduped > # candidates.
This would indicate the fpfBeforeCombo=0 bug where a combo file was written
containing ALL of all_fpf rather than just this combo's contribution."""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

def parse_header(fp):
    cand = None
    dedup = None
    try:
        with open(fp, 'r') as f:
            for i, line in enumerate(f):
                if i > 10:
                    break
                m = re.match(r'# candidates:\s*(\d+)', line)
                if m:
                    cand = int(m.group(1))
                m = re.match(r'# deduped:\s*(\d+)', line)
                if m:
                    dedup = int(m.group(1))
    except Exception:
        pass
    return cand, dedup

anomalies_by_part = {}  # partition -> list of (fname, cand, dedup)
totals_by_part = {}     # partition -> (total_cand, total_dedup)

for name in sorted(os.listdir(BASE)):
    if not (name.startswith('[') and name.endswith(']')):
        continue
    part_dir = os.path.join(BASE, name)
    if not os.path.isdir(part_dir):
        continue
    bad = []
    tc = 0
    td = 0
    for fname in sorted(os.listdir(part_dir)):
        if not fname.endswith('.g') or 'backup' in fname:
            continue
        cand, dedup = parse_header(os.path.join(part_dir, fname))
        if cand is None or dedup is None:
            continue
        tc += cand
        td += dedup
        if dedup > cand:
            bad.append((fname, cand, dedup))
    anomalies_by_part[name] = bad
    totals_by_part[name] = (tc, td)

print(f"{'Partition':<22} {'#anom':>6} {'Sum_dedup':>12} {'Sum_cand':>12} {'Inflate':>10}")
print("-" * 70)
total_anom = 0
total_extra = 0
for p in sorted(anomalies_by_part.keys()):
    bad = anomalies_by_part[p]
    if not bad:
        continue
    extra = sum(d - c for _, c, d in bad)
    total_anom += len(bad)
    total_extra += extra
    tc, td = totals_by_part[p]
    print(f"{p:<22} {len(bad):>6} {td:>12,} {tc:>12,} {extra:>10,}")

print("-" * 70)
print(f"Total anomalous combo files: {total_anom}")
print(f"Total 'extra' groups (deduped - candidates, summed): {total_extra:,}")
print()

# Show top 10 worst offenders
all_bad = []
for p, bad in anomalies_by_part.items():
    for fn, c, d in bad:
        all_bad.append((p, fn, c, d, d - c))
all_bad.sort(key=lambda x: -x[4])
print("Top 10 worst-offending files (largest dedup - candidate gap):")
for p, fn, c, d, gap in all_bad[:10]:
    print(f"  {p}/{fn}: cand={c}, dedup={d}, gap={gap:,}")
