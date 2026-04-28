"""Estimate how many groups the remaining combos will produce.

For each pending partition:
  - Current total (sum of # deduped from completed combos)
  - Per-combo average
  - Distribution of per-combo sizes (to flag whether big-count combos are
    skewed toward the pending tail)
  - Extrapolate to remaining combo count
"""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

PENDING = {
    "[8,4,2,2,2]":   250,
    "[6,4,4,2,2]":   240,
    "[5,4,3,2,2,2]":  50,
}


def read_dedup_count(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        pass
    return None


def analyze(part_name, expected_total):
    folder = os.path.join(BASE, part_name)
    files = sorted(f for f in os.listdir(folder)
                   if f.endswith(".g") and "corrupted" not in f)
    counts = []
    for f in files:
        n = read_dedup_count(os.path.join(folder, f))
        if n is not None:
            counts.append((f, n))
    counts.sort(key=lambda x: -x[1])  # largest first

    done = len(counts)
    remaining = expected_total - done
    sum_done = sum(n for _, n in counts)
    avg = sum_done / done if done else 0
    largest = counts[:5]
    smallest = counts[-5:] if len(counts) >= 5 else []

    print(f"=== {part_name} ===")
    print(f"  done:      {done}/{expected_total}  (remaining: {remaining})")
    print(f"  sum deduped so far: {sum_done:,}")
    print(f"  average per combo:  {avg:,.0f}")
    print(f"  top 5 largest combos:")
    for f, n in largest:
        print(f"    {n:>7,}  {f}")
    print(f"  bottom 5 smallest:")
    for f, n in smallest:
        print(f"    {n:>7,}  {f}")
    est_remaining_avg = remaining * avg
    # Use median-of-large as alternative estimate (if largest combos already done)
    top_decile = counts[:max(1, done // 10)]
    p90_median = sorted(n for _, n in top_decile)[len(top_decile) // 2] if top_decile else 0
    est_remaining_p90 = remaining * p90_median
    print(f"  extrapolated remaining (avg): {est_remaining_avg:,.0f}")
    print(f"  extrapolated remaining (p90 median): {est_remaining_p90:,.0f}")
    print()
    return sum_done, remaining, avg


if __name__ == "__main__":
    total_done = 0
    total_remaining = 0
    total_est_avg = 0
    for p, exp in PENDING.items():
        s, r, a = analyze(p, exp)
        total_done += s
        total_remaining += r
        total_est_avg += r * a

    print("=" * 50)
    print(f"Current groups across 3 pending partitions: {total_done:,}")
    print(f"Remaining combos: {total_remaining}")
    print(f"Estimated new groups (avg extrapolation): {total_est_avg:,.0f}")
    print()
    # Compare to the gap: target = 5,808,293, current grand total = 5,445,773
    # (from count_groups.py), so needed ~= 362,520
    print(f"Needed to hit FPF(S18)=5,808,293: ~362,520 more")
