"""Compare [6,Y] productivity between [6,4,2,2,2,2] (all done) and
[6,4,4,2,2] (~half done). For each [6,Y], compute a ratio that could
predict pending [6,4,4,2,2] combo counts.

[6,4,2,2,2,2] combos: [2,1][2,1][2,1][2,1][4,a][6,Y]  — 1 D_4-slot, 1 S_6-slot
[6,4,4,2,2]   combos: [2,1][2,1][4,a][4,b][6,Y]       — 2 D_4-slots, 1 S_6-slot
"""
import os
import re
from collections import defaultdict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
P_SRC = os.path.join(BASE, "[6,4,2,2,2,2]")  # reference (fully done)
P_TGT = os.path.join(BASE, "[6,4,4,2,2]")     # currently running


def dedup(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        return None
    return None


# Read all [6,4,2,2,2,2] combos: key = (a, Y)
src = {}
src_pat = re.compile(r"\[2,1\]_\[2,1\]_\[2,1\]_\[2,1\]_\[4,(\d+)\]_\[6,(\d+)\]\.g")
for f in os.listdir(P_SRC):
    m = src_pat.match(f)
    if m:
        a, Y = int(m.group(1)), int(m.group(2))
        n = dedup(os.path.join(P_SRC, f))
        if n is not None:
            src[(a, Y)] = n

# Read all [6,4,4,2,2] combos: key = (a, b, Y) with a <= b
tgt = {}
tgt_pat = re.compile(r"\[2,1\]_\[2,1\]_\[4,(\d+)\]_\[4,(\d+)\]_\[6,(\d+)\]\.g")
for f in os.listdir(P_TGT):
    if "corrupted" in f:
        continue
    m = tgt_pat.match(f)
    if m:
        a, b, Y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        n = dedup(os.path.join(P_TGT, f))
        if n is not None:
            tgt[(a, b, Y)] = n

# For each [6,Y], aggregate source (sum over a) and target (sum over a,b pairs)
# Also aggregate by-[4,X] family to see if per-D_4-type productivity is consistent.
by_Y_src_sum = defaultdict(int)
by_Y_tgt_sum = defaultdict(int)
by_Y_tgt_n = defaultdict(int)
by_Y_src_n = defaultdict(int)
for (a, Y), n in src.items():
    by_Y_src_sum[Y] += n
    by_Y_src_n[Y] += 1
for (a, b, Y), n in tgt.items():
    by_Y_tgt_sum[Y] += n
    by_Y_tgt_n[Y] += 1

# Print ratio per [6,Y] for Ys present in both
print(f"{'[6,Y]':>6} | {'src sum':>10} ({'n':>2}) | {'tgt sum':>10} ({'n':>2}) | "
      f"{'tgt/src':>8} | {'tgt_expected_combos':>5}")
print("-" * 80)
all_Y = sorted(set(list(by_Y_src_sum.keys()) + list(by_Y_tgt_sum.keys())))
ratios_by_Y = {}
for Y in all_Y:
    s_sum = by_Y_src_sum.get(Y, 0)
    t_sum = by_Y_tgt_sum.get(Y, 0)
    s_n = by_Y_src_n.get(Y, 0)
    t_n = by_Y_tgt_n.get(Y, 0)
    ratio = t_sum / s_sum if s_sum > 0 else 0
    ratios_by_Y[Y] = ratio
    # Expected number of target combos per Y:
    # For [6,4,4,2,2], sorted (a,b) with a<=b, a,b in [1..5]: C(5+2-1,2) = 15
    # per [6,Y]. Total 16 Ys x 15 = 240. Done combos vary.
    print(f"{Y:>6} | {s_sum:>10,} ({s_n:>2}) | {t_sum:>10,} ({t_n:>2}) | "
          f"{ratio:>8.2f} | (15 combos per Y)")

# For the pending [6,Y] in target, estimate using avg ratio from done Ys
# Pending target combos are those (a,b,Y) not in tgt.
pending_by_Y = defaultdict(int)
for a in range(1, 6):
    for b in range(a, 6):
        for Y in range(1, 17):
            if (a, b, Y) not in tgt:
                pending_by_Y[Y] += 1

# Estimate pending contribution per Y
print()
print("Projecting pending contribution for [6,4,4,2,2]:")
print(f"{'[6,Y]':>6} | {'pending':>7} | {'per-combo avg (done)':>20} | "
      f"{'extrap':>10}")
print("-" * 64)
total_est = 0
for Y in range(1, 17):
    pending = pending_by_Y[Y]
    done_n = by_Y_tgt_n.get(Y, 0)
    done_sum = by_Y_tgt_sum.get(Y, 0)
    if pending == 0:
        continue
    # Use per-combo average from done combos of this Y in the target partition
    if done_n > 0:
        per_combo = done_sum / done_n
    else:
        # No done combos for this Y — use source ratio
        # Source has 5 combos per Y; target has 15 per Y.
        # If source/target ratio is R, then per-target-combo avg approx
        # src_avg * (R/3) — very rough
        src_n = by_Y_src_n.get(Y, 0)
        if src_n > 0:
            src_avg = by_Y_src_sum[Y] / src_n
        else:
            src_avg = 0
        per_combo = src_avg * 3  # rough — tgt has 3x the combos per Y
    est = pending * per_combo
    total_est += est
    print(f"{Y:>6} | {pending:>7} | {per_combo:>20,.0f} | {est:>10,.0f}")
print()
print(f"Rough estimate of pending [6,4,4,2,2] contribution: {total_est:,.0f}")
