"""Check duplication multiplicity for the 3 affected partitions."""
import os
from collections import Counter

GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"

def load_gens(filepath):
    groups = []
    buf = ""
    with open(filepath, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.endswith('\\'):
                buf += line[:-1]
            else:
                buf += line
                if buf.strip() and len(buf.strip()) > 2:
                    groups.append(buf.strip())
                buf = ""
    return groups

for part_str in ["6_5_4_2", "8_5_4", "6_4_3_2_2"]:
    filepath = os.path.join(GENS_DIR, f"gens_{part_str}.txt")
    groups = load_gens(filepath)

    # Count occurrences of each group
    counts = Counter(groups)

    # Distribution of multiplicities
    mult_dist = Counter(counts.values())

    print(f"\n=== [{part_str}] ===")
    print(f"  Total entries: {len(groups)}")
    print(f"  Unique groups: {len(counts)}")
    print(f"  Multiplicity distribution:")
    for mult in sorted(mult_dist.keys()):
        print(f"    appears {mult}x: {mult_dist[mult]} groups")

    # Verify: sum of (mult * count) should equal total
    total_check = sum(mult * cnt for mult, cnt in mult_dist.items())
    print(f"  Check: sum = {total_check} (expected {len(groups)})")
