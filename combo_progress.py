"""Compute expected total combos vs completed combos per partition."""
import os
from math import comb

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

NR_TRANSITIVE = {
    2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50, 9: 34,
    10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104,
    16: 1954, 17: 5, 18: 983,
}


def expected_combos(partition):
    from collections import Counter
    mults = Counter(partition)
    total = 1
    for d, m in mults.items():
        n = NR_TRANSITIVE[d]
        # Multiset of size m from n options: C(n+m-1, m)
        total *= comb(n + m - 1, m)
    return total


def count_completed(part_dir):
    if not os.path.isdir(part_dir):
        return 0
    return sum(
        1 for f in os.listdir(part_dir)
        if f.endswith('.g') and 'backup' not in f and 'Copy' not in f
    )


partitions = []
for name in sorted(os.listdir(BASE)):
    if name.startswith('[') and name.endswith(']') and os.path.isdir(os.path.join(BASE, name)):
        p = [int(x) for x in name[1:-1].split(',')]
        partitions.append((name, p))

print(f"{'Partition':<22} {'Expected':>10} {'Done':>8} {'Remaining':>10} {'Done%':>6}")
print("-" * 60)
grand_expected = 0
grand_done = 0
for name, p in partitions:
    exp = expected_combos(p)
    done = count_completed(os.path.join(BASE, name))
    remain = exp - done
    grand_expected += exp
    grand_done += done
    if remain > 0:
        pct = 100.0 * done / exp if exp > 0 else 0
        print(f"{name:<22} {exp:>10,} {done:>8,} {remain:>10,} {pct:>5.1f}%")

print("-" * 60)
print(f"{'TOTAL':<22} {grand_expected:>10,} {grand_done:>8,} "
      f"{grand_expected - grand_done:>10,} "
      f"{100 * grand_done / grand_expected:>5.1f}%")
print()
print(f"Completed: {grand_done:,} / {grand_expected:,} combos "
      f"({100 * grand_done / grand_expected:.1f}%)")
print(f"Remaining: {grand_expected - grand_done:,} combos")
