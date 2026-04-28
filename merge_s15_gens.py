"""
Merge S15 generator files:
- Use _fixed.txt for [5,4,4,2] and [6,6,3] (recomputed with orbital OFF)
- Use original .txt for all other partitions
- Output: combined file with all 159,129 - 75,154 = 83,975 FPF classes
  plus the non-FPF classes from lift_cache

The non-FPF classes (partitions with 1-parts) total 159,129 - 83,975 = 75,154.
These are computed by CountAllConjugacyClassesFast from lower-degree data.
"""

import os
import re

gens_dir = r"C:\Users\jeffr\Downloads\Lifting\parallel_s15\gens"
output_file = r"C:\Users\jeffr\Downloads\Lifting\parallel_s15\s15_all_fpf_gens.txt"

# The two affected partitions
affected = {"5_4_4_2", "6_6_3"}

total = 0
partition_counts = {}

with open(output_file, "w") as out:
    for fname in sorted(os.listdir(gens_dir)):
        if not fname.startswith("gens_") or not fname.endswith(".txt"):
            continue
        # Skip _fixed files in the main loop
        if "_fixed" in fname:
            continue

        # Extract partition string
        m = re.match(r"gens_(.+)\.txt$", fname)
        if not m:
            continue
        part_str = m.group(1)

        # Use fixed version for affected partitions
        if part_str in affected:
            fixed_fname = f"gens_{part_str}_fixed.txt"
            fixed_path = os.path.join(gens_dir, fixed_fname)
            if os.path.exists(fixed_path):
                src = fixed_path
                label = f"{part_str} (FIXED)"
            else:
                print(f"WARNING: {fixed_fname} not found! Using original (buggy) {fname}")
                src = os.path.join(gens_dir, fname)
                label = f"{part_str} (BUGGY - fixed file missing)"
        else:
            src = os.path.join(gens_dir, fname)
            label = part_str

        # Count and copy
        count = 0
        with open(src, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    out.write(line + "\n")
                    count += 1

        partition_counts[part_str] = count
        total += count
        print(f"  [{part_str.replace('_', ',')}]: {count} classes  ({label})")

print(f"\nTotal FPF classes: {total}")
print(f"Expected: 83975")
print(f"Match: {'YES' if total == 83975 else 'NO (deficit: ' + str(83975 - total) + ')'}")
print(f"\nOutput: {output_file}")

# Also write a summary file
summary_file = r"C:\Users\jeffr\Downloads\Lifting\parallel_s15\s15_fpf_summary.txt"
with open(summary_file, "w") as f:
    f.write(f"S15 FPF Conjugacy Classes Summary\n")
    f.write(f"{'='*50}\n")
    f.write(f"Total FPF classes: {total}\n")
    f.write(f"Expected (OEIS): 83975\n\n")
    for part_str in sorted(partition_counts.keys(),
                           key=lambda s: [int(x) for x in s.split("_")],
                           reverse=True):
        parts = part_str.split("_")
        f.write(f"  [{','.join(parts)}]: {partition_counts[part_str]}\n")
print(f"Summary: {summary_file}")
