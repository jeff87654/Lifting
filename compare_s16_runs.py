#!/usr/bin/env python3
"""Compare old vs fresh S16 partition counts."""

# Old run counts (from parallel_s16/worker_*_results.txt)
# For partitions with multiple results, using the latest (highest worker#)
old = {
    (16,): 1954,
    (14,2): 134,
    (13,3): 26,
    (12,4): 8167,
    (12,2,2): 3414,
    (11,5): 51,
    (11,3,2): 39,
    (10,6): 2547,
    (10,4,2): 4329,
    (10,3,3): 681,
    (10,2,2,2): 1072,
    (9,7): 392,
    (9,5,2): 847,
    (9,4,3): 3146,
    (9,3,2,2): 1262,
    (8,8): 20082,
    (8,6,2): 29440,
    (8,5,3): 3594,
    (8,4,4): 80189,
    (8,4,2,2): 62639,
    (8,3,3,2): 6341,
    (8,2,2,2,2): 8019,
    (7,7,2): 94,
    (7,6,3): 955,
    (7,5,4): 633,
    (7,5,2,2): 277,
    (7,4,3,2): 1117,
    (7,3,3,3): 216,
    (7,3,2,2,2): 287,
    (6,6,4): 21109,
    (6,6,2,2): 9107,
    (6,5,5): 1283,
    (6,5,3,2): 3311,
    (6,4,4,2): 28551,
    (6,4,3,3): 9885,
    (6,4,2,2,2): 22752,
    (6,3,3,2,2): 4174,
    (6,2,2,2,2,2): 2456,
    (5,5,4,2): 1864,
    (5,5,3,3): 356,
    (5,5,2,2,2): 482,
    (5,4,4,3): 5731,
    (5,4,3,2,2): 4390,
    (5,3,3,3,2): 494,
    (5,3,2,2,2,2): 694,
    (4,4,4,4): 38339,
    (4,4,4,2,2): 33416,
    (4,4,3,3,2): 12296,
    (4,4,2,2,2,2): 18376,
    (4,3,3,3,3): 1046,
    (4,3,3,2,2,2): 4734,
    (4,2,2,2,2,2,2): 2571,
    (3,3,3,3,2,2): 419,
    (3,3,2,2,2,2,2): 553,
    (2,2,2,2,2,2,2,2): 194,
}

# Fresh run counts (from parallel_s16_fresh/worker_*_results.txt)
fresh = {
    (16,): None,        # W24 pending
    (14,2): 142,
    (13,3): 26,
    (12,4): 8167,
    (12,2,2): 3414,
    (11,5): 51,
    (11,3,2): 39,
    (10,6): 2547,
    (10,4,2): 4329,
    (10,3,3): 681,
    (10,2,2,2): 1072,
    (9,7): 392,
    (9,5,2): 847,
    (9,4,3): 3146,
    (9,3,2,2): 1262,
    (8,8): 20082,
    (8,6,2): None,      # W17 in progress (~combo 696/800)
    (8,5,3): 3594,
    (8,4,4): 80189,
    (8,4,2,2): 62751,
    (8,3,3,2): 6341,
    (8,2,2,2,2): 8019,
    (7,7,2): 94,
    (7,6,3): 955,
    (7,5,4): 633,
    (7,5,2,2): 277,
    (7,4,3,2): 1117,
    (7,3,3,3): 216,
    (7,3,2,2,2): 287,
    (6,6,4): 21109,
    (6,6,2,2): 9107,
    (6,5,5): 1276,
    (6,5,3,2): 3311,
    (6,4,4,2): 60967,
    (6,4,3,3): 9885,
    (6,4,2,2,2): 22922,
    (6,3,3,2,2): 4174,
    (6,2,2,2,2,2): 2456,
    (5,5,4,2): 1864,
    (5,5,3,3): 356,
    (5,5,2,2,2): 482,
    (5,4,4,3): 5731,
    (5,4,3,2,2): 4390,
    (5,3,3,3,2): 494,
    (5,3,2,2,2,2): 694,
    (4,4,4,4): 35562,
    (4,4,4,2,2): 57226,
    (4,4,3,3,2): 12296,
    (4,4,2,2,2,2): 18376,
    (4,3,3,3,3): 1046,
    (4,3,3,2,2,2): 4734,
    (4,2,2,2,2,2,2): 2571,
    (3,3,3,3,2,2): 419,
    (3,3,2,2,2,2,2): 553,
    (2,2,2,2,2,2,2,2): None,  # W24 starting
}

OEIS_TOTAL = 686165
INHERITED = 159129
OEIS_FPF = OEIS_TOTAL - INHERITED  # 527036

def fmt_part(p):
    return "[" + ",".join(str(x) for x in p) + "]"

def main():
    # Sort partitions: by number of parts, then by parts descending
    partitions = sorted(old.keys(), key=lambda p: (-max(p), len(p), p))
    # Actually sort by descending partition in standard order
    partitions = sorted(old.keys(), key=lambda p: list(p))
    # Better: sort by partition in reverse lex
    partitions = sorted(old.keys(), reverse=True)

    print(f"{'Partition':>22s}  {'Old':>7s}  {'Fresh':>7s}  {'Diff':>7s}  {'Note'}")
    print(f"{'-'*22}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*20}")

    old_total = 0
    fresh_total = 0
    n_match = 0
    n_diff = 0
    n_pending = 0
    diffs = []

    for p in partitions:
        o = old[p]
        f = fresh.get(p)
        old_total += o

        p_str = fmt_part(p)

        if f is None:
            fresh_str = "..."
            diff_str = ""
            note = "in progress"
            n_pending += 1
        elif f == o:
            fresh_total += f
            fresh_str = str(f)
            diff_str = "0"
            note = ""
            n_match += 1
        else:
            fresh_total += f
            diff = f - o
            fresh_str = str(f)
            diff_str = f"{diff:+d}"
            if diff > 0:
                note = "FRESH HIGHER"
            else:
                note = "OLD HIGHER"
            n_diff += 1
            diffs.append((p, o, f, diff))

        print(f"{p_str:>22s}  {o:>7d}  {fresh_str:>7s}  {diff_str:>7s}  {note}")

    print(f"{'-'*22}  {'-'*7}  {'-'*7}  {'-'*7}")
    print(f"{'Sum (completed)':>22s}  {old_total:>7d}  {fresh_total:>7d}  {fresh_total - old_total:>+7d}")
    print(f"{'+ inherited':>22s}  {INHERITED:>7d}  {INHERITED:>7d}")

    old_s16 = old_total + INHERITED
    fresh_s16 = fresh_total + INHERITED
    print(f"{'= S16 total':>22s}  {old_s16:>7d}  {fresh_s16:>7d}  {fresh_s16 - old_s16:>+7d}")
    print(f"{'OEIS target':>22s}  {OEIS_TOTAL:>7d}  {OEIS_TOTAL:>7d}")
    print(f"{'Deficit':>22s}  {old_s16 - OEIS_TOTAL:>+7d}  {fresh_s16 - OEIS_TOTAL:>+7d}")

    print(f"\nSummary: {n_match} match, {n_diff} differ, {n_pending} pending")

    if diffs:
        print(f"\n{'='*60}")
        print(f"Partitions with differences:")
        print(f"{'='*60}")
        print(f"{'Partition':>22s}  {'Old':>7s}  {'Fresh':>7s}  {'Diff':>7s}  {'%':>6s}")
        print(f"{'-'*22}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*6}")
        for p, o, f, d in sorted(diffs, key=lambda x: -abs(x[3])):
            pct = (d / o * 100) if o else 0
            print(f"{fmt_part(p):>22s}  {o:>7d}  {f:>7d}  {d:>+7d}  {pct:>+5.1f}%")

if __name__ == '__main__':
    main()
