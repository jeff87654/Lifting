"""List the specific missing combos per pending partition by enumerating
the expected (non-decreasing TI) keys and diffing against present files."""
import os
import re
from itertools import combinations_with_replacement

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
NR_TG = {2:1, 3:2, 4:5, 5:5, 6:16, 7:7, 8:50, 9:34, 10:45, 11:8,
         12:301, 13:9, 14:63, 15:104, 16:1954, 17:10, 18:983}


def enum_combos(parts):
    """Enumerate combo keys as sorted (degree, TI) multiset strings, matching
    _CacheKeyToFileName's output format."""
    # Group parts by degree
    from collections import Counter
    deg_counts = Counter(parts)
    # For each degree, list the multisets of TIs (non-decreasing, size = count)
    per_degree_sets = []
    for d, k in sorted(deg_counts.items()):
        mset_list = list(combinations_with_replacement(range(1, NR_TG[d] + 1), k))
        per_degree_sets.append([(d, ms) for ms in mset_list])
    # Cartesian product across degrees
    result = []
    def recurse(idx, picked):
        if idx == len(per_degree_sets):
            # Merge all picked (d, ms) into sorted (d, ti) pairs
            pairs = []
            for d, ms in picked:
                for t in ms:
                    pairs.append((d, t))
            pairs.sort()
            result.append(pairs)
            return
        for opt in per_degree_sets[idx]:
            picked.append(opt)
            recurse(idx + 1, picked)
            picked.pop()
    recurse(0, [])
    return result


def combo_filename(pairs):
    return "_".join(f"[{d},{t}]" for d, t in pairs) + ".g"


def main():
    for part_name, parts in [("[8,4,2,2,2]", [8,4,2,2,2]),
                              ("[6,4,4,2,2]", [6,4,4,2,2]),
                              ("[5,4,3,2,2,2]", [5,4,3,2,2,2])]:
        folder = os.path.join(BASE, part_name)
        existing = set(f for f in os.listdir(folder)
                       if f.endswith(".g") and "corrupted" not in f)
        expected = enum_combos(parts)
        exp_names = [combo_filename(p) for p in expected]
        missing = [n for n in exp_names if n not in existing]
        print(f"=== {part_name} ===")
        print(f"  expected {len(expected)}, present {len(existing)}, missing {len(missing)}")
        # Summarise missing by the "interesting" factor TI (non-size-2)
        print(f"  first 15 missing:")
        for n in missing[:15]:
            print(f"    {n}")
        print(f"  last 10 missing:")
        for n in missing[-10:]:
            print(f"    {n}")
        print()


if __name__ == "__main__":
    main()
