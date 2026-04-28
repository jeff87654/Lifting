"""Three-way comparison across the bug-fix evolution:
  - parallel_s18_prebugfix_backup/  : original, both bugs present
  - parallel_s18_bugfix1_backup/    : after fix #1 only (some combos regenerated)
  - parallel_s18/                   : current state (fix #1 + fix #2)
"""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
PREBUG = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18_prebugfix_backup"
FIX1 = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18_bugfix1_backup"


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


def load_all(root):
    """Return dict keyed by (partition, filename) -> dedup count."""
    out = {}
    if not os.path.isdir(root):
        return out
    for partition in os.listdir(root):
        pdir = os.path.join(root, partition)
        if not os.path.isdir(pdir): continue
        for f in os.listdir(pdir):
            if not f.endswith(".g"): continue
            out[(partition, f)] = dedup(os.path.join(pdir, f))
    return out


def main():
    prebug = load_all(PREBUG)
    fix1 = load_all(FIX1)
    current = load_all(BASE)

    # Filter current to only affected combos (those in prebug)
    # so we aren't comparing partition-wide
    total = len(prebug)
    print(f"Affected combos (baseline pre-bugfix): {total}")
    print()

    # Compare fix1 vs prebug (the stopped fix-1 rerun)
    f1_complete = sum(1 for k in prebug if k in fix1)
    f1_bigger = [(k[0], k[1], prebug[k], fix1[k]) for k in prebug
                 if k in fix1 and fix1[k] is not None and prebug[k] is not None
                 and fix1[k] > prebug[k]]
    f1_smaller = [(k[0], k[1], prebug[k], fix1[k]) for k in prebug
                  if k in fix1 and fix1[k] is not None and prebug[k] is not None
                  and fix1[k] < prebug[k]]
    f1_same = f1_complete - len(f1_bigger) - len(f1_smaller)
    f1_gain = sum(b[3] - b[2] for b in f1_bigger)
    f1_loss = sum(b[3] - b[2] for b in f1_smaller)

    print(f"--- Fix-1 vs Prebugfix (fix-1 stopped partway) ---")
    print(f"Fix-1 rerun complete:  {f1_complete}")
    print(f"  bigger: {len(f1_bigger)}  total gain: {f1_gain:+,}")
    print(f"  same:   {f1_same}")
    print(f"  smaller:{len(f1_smaller)}  total loss: {f1_loss:+,}")
    print()

    # Compare current (fix-2) vs prebug
    cur_complete = sum(1 for k in prebug if k in current)
    cur_pending = total - cur_complete
    cur_bigger = [(k[0], k[1], prebug[k], current[k]) for k in prebug
                  if k in current and current[k] is not None and prebug[k] is not None
                  and current[k] > prebug[k]]
    cur_smaller = [(k[0], k[1], prebug[k], current[k]) for k in prebug
                   if k in current and current[k] is not None and prebug[k] is not None
                   and current[k] < prebug[k]]
    cur_same = cur_complete - len(cur_bigger) - len(cur_smaller)
    cur_gain = sum(b[3] - b[2] for b in cur_bigger)
    cur_loss = sum(b[3] - b[2] for b in cur_smaller)

    print(f"--- Current (fix-2) vs Prebugfix ---")
    print(f"Rerun complete: {cur_complete}  (pending: {cur_pending})")
    print(f"  bigger: {len(cur_bigger)}  total gain: {cur_gain:+,}")
    print(f"  same:   {cur_same}")
    print(f"  smaller:{len(cur_smaller)}  total loss: {cur_loss:+,}")
    print()

    # Compare current vs fix1 (what fix-2 added on top of fix-1)
    both = [k for k in prebug if k in current and k in fix1]
    f2_diff = [(k[0], k[1], fix1[k], current[k]) for k in both
               if fix1[k] is not None and current[k] is not None
               and fix1[k] != current[k]]
    f2_bigger = [d for d in f2_diff if d[3] > d[2]]
    f2_smaller = [d for d in f2_diff if d[3] < d[2]]
    f2_gain = sum(d[3] - d[2] for d in f2_bigger)
    f2_loss = sum(d[3] - d[2] for d in f2_smaller)

    print(f"--- Current (fix-2) vs Fix-1 (overlap: {len(both)} combos) ---")
    print(f"  bigger: {len(f2_bigger)}  gain over fix1: {f2_gain:+,}")
    print(f"  smaller:{len(f2_smaller)}  loss vs fix1:   {f2_loss:+,}")
    print()

    if cur_bigger:
        print("Top 15 biggest gains (vs prebug):")
        print(f"{'partition':<22} {'combo':<50} {'pre':>7} {'now':>7} {'d':>6}")
        print("-" * 96)
        for p, f, o, n in sorted(cur_bigger, key=lambda x: -(x[3]-x[2]))[:15]:
            print(f"{p:<22} {f[:48]:<50} {o:>7,} {n:>7,} {n-o:>+6,}")
    if cur_smaller:
        print()
        print(f"REGRESSIONS vs prebug ({len(cur_smaller)}):")
        for p, f, o, n in cur_smaller[:15]:
            print(f"  {p}/{f}: {o} -> {n} ({n-o:+})")


if __name__ == "__main__":
    main()
