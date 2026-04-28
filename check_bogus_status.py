"""Did the 26 partitions backed up as bogus get re-computed?

For each _bogus_backup_* tar.gz, check if the live partition folder has
enough combo files to match the expected combo count. Report per-partition
status and group counts.
"""
import os
import re
import glob
from math import comb

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

NR_TG = {2:1, 3:2, 4:5, 5:5, 6:16, 7:7, 8:50, 9:34, 10:45, 11:8,
         12:301, 13:9, 14:63, 15:104, 16:1954, 17:10, 18:983}


def expected_combos(parts):
    counts = {}
    for d in parts:
        counts[d] = counts.get(d, 0) + 1
    total = 1
    for d, k in counts.items():
        total *= comb(NR_TG[d] + k - 1, k)
    return total


def read_dedup(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        pass
    return None


def main():
    # Find all _bogus_backup_ tar.gz files
    bogus_files = glob.glob(os.path.join(BASE, "*_bogus_backup_*.tar.gz"))
    print(f"Found {len(bogus_files)} bogus backups")

    total_redone = 0
    total_missing = 0
    total_groups_redone = 0
    rerun_needed = []

    for bpath in sorted(bogus_files):
        bname = os.path.basename(bpath)
        # Extract partition name: "[10,5,3]_bogus_backup_20260415_171425.tar.gz"
        m = re.match(r"(\[[^\]]+\])_bogus_backup_", bname)
        if not m:
            continue
        part_name = m.group(1)
        parts = [int(x) for x in part_name[1:-1].split(",")]
        expected = expected_combos(parts)
        folder = os.path.join(BASE, part_name)
        if not os.path.isdir(folder):
            print(f"  {part_name}: LIVE FOLDER MISSING (not re-run)")
            total_missing += 1
            rerun_needed.append(part_name)
            continue
        files = [f for f in os.listdir(folder)
                 if f.endswith(".g") and "corrupted" not in f]
        actual = len(files)
        if actual < expected:
            print(f"  {part_name}: {actual}/{expected} combos — INCOMPLETE")
            total_missing += 1
            rerun_needed.append(part_name)
        else:
            groups = sum(read_dedup(os.path.join(folder, f)) or 0 for f in files)
            print(f"  {part_name}: {actual}/{expected} combos, {groups:,} groups")
            total_redone += 1
            total_groups_redone += groups

    print()
    print(f"Re-done partitions: {total_redone}/{len(bogus_files)}")
    print(f"Still incomplete:   {total_missing}")
    print(f"Groups in re-done bogus partitions: {total_groups_redone:,}")
    if rerun_needed:
        print("\nPartitions that still need to be re-run:")
        for p in rerun_needed:
            print(f"  {p}")


if __name__ == "__main__":
    main()
