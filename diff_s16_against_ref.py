"""Compare m6m7 S_16 per-partition counts against the reference derived
from s17_orbit_type_counts.txt (S_17 orbit types with a trailing 1)."""
import re
from pathlib import Path

S17_FILE = Path(r"C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s17_orbit_type_counts.txt")
M6M7_DIR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7")

# Read S_17 orbit counts
s17 = {}
with open(S17_FILE) as f:
    for line in f:
        m = re.match(r"^\[([\d,]+)\]\s+(\d+)", line.strip())
        if m:
            parts = tuple(int(x) for x in m.group(1).split(","))
            s17[parts] = int(m.group(2))

# Compute S_16 reference counts from S_17's [..., 1] entries.
# For an S_16 FPF partition p of 16, S_17 orbit type is sorted(p + [1]).
def s17_for_s16(p):
    # p = tuple of parts summing to 16; add a 1 and sort descending
    merged = tuple(sorted(list(p) + [1], reverse=True))
    return s17.get(merged)

# Read m6m7 per-partition counts from summary.txt
m6m7 = {}
for d in sorted(M6M7_DIR.glob("[[]*[]]")):
    name = d.name
    parts_str = name.strip("[]")
    parts = tuple(int(x) for x in parts_str.split(","))
    summary = d / "summary.txt"
    if summary.exists():
        with open(summary) as f:
            for line in f:
                if line.startswith("total_classes:"):
                    cnt = int(line.split(":")[1].strip())
                    m6m7[parts] = cnt
                    break

# Compare
total_m6m7 = 0
total_ref = 0
print(f"{'partition':<30} {'ours':>8} {'ref':>8} {'delta':>6}")
print("-" * 60)
mismatches = []
for parts in sorted(m6m7.keys()):
    our_cnt = m6m7[parts]
    ref_cnt = s17_for_s16(parts)
    delta = ""
    if ref_cnt is None:
        delta = "(no ref)"
    else:
        d = our_cnt - ref_cnt
        delta = f"{d:+d}" if d != 0 else "0"
        total_ref += ref_cnt
        if d != 0:
            mismatches.append((parts, our_cnt, ref_cnt, d))
    total_m6m7 += our_cnt
    print(f"{str(parts):<30} {our_cnt:>8} {ref_cnt if ref_cnt is not None else '-':>8} {delta:>6}")

print("-" * 60)
print(f"{'TOTAL':<30} {total_m6m7:>8} {total_ref:>8} {total_m6m7 - total_ref:+d}")
print()
if mismatches:
    print("=== MISMATCHES ===")
    for parts, ours, ref, delta in mismatches:
        print(f"  {parts}: ours={ours}, ref={ref}, delta={delta:+d}")
else:
    print("All partitions match!")
