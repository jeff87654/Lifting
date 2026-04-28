"""Forecast final count based on current state and source-partition ratios."""
import os, re
from collections import defaultdict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
P_SRC = os.path.join(BASE, "[6,4,2,2,2,2]")
P_TGT = os.path.join(BASE, "[6,4,4,2,2]")


def dedup(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m: return int(m.group(1))
    except OSError: return None
    return None


src_by_Y = defaultdict(int)  # sum of dedup across 5 [4,a][6,Y] combos
src_pat = re.compile(r"\[2,1\]_\[2,1\]_\[2,1\]_\[2,1\]_\[4,(\d+)\]_\[6,(\d+)\]\.g")
for f in os.listdir(P_SRC):
    m = src_pat.match(f)
    if m:
        Y = int(m.group(2))
        n = dedup(os.path.join(P_SRC, f))
        if n: src_by_Y[Y] += n

tgt_done_by_Y = defaultdict(int)
tgt_done_count = defaultdict(int)
tgt_pat = re.compile(r"\[2,1\]_\[2,1\]_\[4,(\d+)\]_\[4,(\d+)\]_\[6,(\d+)\]\.g")
for f in os.listdir(P_TGT):
    if "corrupted" in f: continue
    m = tgt_pat.match(f)
    if m:
        Y = int(m.group(3))
        n = dedup(os.path.join(P_TGT, f))
        if n is not None:
            tgt_done_by_Y[Y] += n
            tgt_done_count[Y] += 1

# Compute ratio from FULLY-DONE Ys
ratios = {}
for Y in range(1, 17):
    if tgt_done_count[Y] == 15 and src_by_Y[Y] > 0:
        ratios[Y] = tgt_done_by_Y[Y] / src_by_Y[Y]

# Use average ratio from "tiny" and "standard" families to predict tiny/standard Ys
# Tiny: src < 500; Standard: 1000-3000; Productive: big
tiny_Ys = [Y for Y in ratios if src_by_Y[Y] < 500]
std_Ys  = [Y for Y in ratios if 1000 < src_by_Y[Y] < 3000]
prod_Ys = [Y for Y in ratios if src_by_Y[Y] >= 10000]

def avg(lst): return sum(lst)/len(lst) if lst else 0
r_tiny = avg([ratios[Y] for Y in tiny_Ys])
r_std  = avg([ratios[Y] for Y in std_Ys])
r_prod = avg([ratios[Y] for Y in prod_Ys])
print(f"Avg ratio (tiny, src<500):        {r_tiny:.2f} from Ys {tiny_Ys}")
print(f"Avg ratio (standard, 1k-3k):      {r_std:.2f} from Ys {std_Ys}")
print(f"Avg ratio (productive, >10k):     {r_prod:.2f} from Ys {prod_Ys}")
print()

print(f"{'Y':>3} | {'src':>8} | {'done n':>6} | {'done sum':>10} | "
      f"{'predicted full':>14} | {'remaining':>10}")
print("-" * 70)
grand_remaining = 0
grand_done = 0
for Y in range(1, 17):
    s = src_by_Y[Y]
    done_n = tgt_done_count[Y]
    done_sum = tgt_done_by_Y[Y]
    grand_done += done_sum
    if done_n == 15:
        predicted = done_sum
        remaining = 0
    else:
        # Use ratio matching the category of this Y
        if s < 500:
            ratio = r_tiny
        elif s < 10000:
            ratio = r_std
        else:
            ratio = r_prod
        predicted = s * ratio
        remaining = max(0, predicted - done_sum)
    print(f"{Y:>3} | {s:>8,} | {done_n:>6} | {done_sum:>10,} | "
          f"{predicted:>14,.0f} | {remaining:>10,.0f}")
    grand_remaining += remaining

print()
print(f"Target partition current total done: {grand_done:,}")
print(f"Forecasted remaining contribution:   {grand_remaining:,.0f}")
print(f"Forecasted partition total:          {grand_done + grand_remaining:,.0f}")

# Overall S18 total projection
# Read the full count
import subprocess
result = subprocess.run(['python', 'count_groups.py'], capture_output=True, text=True)
for line in result.stdout.splitlines():
    if 'GRAND TOTAL (headers)' in line:
        current_total = int(line.split(':')[1].replace(',','').strip())
        break
# current_total includes this partition's done total already
projected_s18_total = current_total + grand_remaining
target = 5_808_293
print()
print(f"Current S18 FPF total: {current_total:,}")
print(f"Projected final:       {projected_s18_total:,.0f}")
print(f"Target FPF(S18):       {target:,}")
print(f"Projected gap:         {target - projected_s18_total:+,.0f}")
