"""Check all gens files for checkpoint double-loading duplicates."""
import os
import re

GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"
RESULTS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17"

def load_gens(filepath):
    """Load gens file, handling \\ line continuations."""
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

def find_duplicates(groups):
    """Find duplicate groups by exact string match. Returns (unique_count, dup_info)."""
    seen = {}
    dups = 0
    for i, g in enumerate(groups):
        if g in seen:
            dups += 1
        else:
            seen[g] = i
    return len(groups) - dups, dups

# Get expected counts from results files
expected = {}
for f in os.listdir(RESULTS_DIR):
    if f.startswith("worker_") and f.endswith("_results.txt"):
        fpath = os.path.join(RESULTS_DIR, f)
        try:
            with open(fpath, 'r') as rf:
                for line in rf:
                    line = line.strip()
                    if not line or line.startswith("TOTAL") or line.startswith("TIME"):
                        continue
                    # Format: [6, 5, 4, 2] 80076 or [6,5,4,2] 80076
                    m = re.match(r'\[([^\]]+)\]\s+(\d+)', line)
                    if m:
                        parts = m.group(1).replace(' ', '')
                        count = int(m.group(2))
                        expected[parts] = count
        except:
            pass

print(f"Found {len(expected)} partition results\n")

# Check each gens file
total_overcounted = 0
problems = []
for f in sorted(os.listdir(GENS_DIR)):
    if not f.startswith("gens_") or not f.endswith(".txt"):
        continue
    part_str = f[5:-4]  # e.g., "6_5_4_2"
    key = part_str.replace("_", ",")

    filepath = os.path.join(GENS_DIR, f)
    groups = load_gens(filepath)
    unique_count, dup_count = find_duplicates(groups)

    exp = expected.get(key, "?")

    if dup_count > 0:
        status = f"DUPLICATES: {dup_count} dupes, {unique_count} unique"
        problems.append((part_str, len(groups), unique_count, dup_count, exp))
        total_overcounted += dup_count
    elif len(groups) != exp and exp != "?":
        status = f"COUNT MISMATCH: {len(groups)} in gens vs {exp} in results"
        problems.append((part_str, len(groups), unique_count, 0, exp))
    else:
        status = f"OK ({len(groups)} groups)"

    if dup_count > 0 or (len(groups) != exp and exp != "?"):
        print(f"  [{part_str}]: {status}")

print(f"\n=== Summary ===")
print(f"Total partitions with duplicates/mismatches: {len(problems)}")
print(f"Total overcounted: {total_overcounted}")
for part_str, total, unique, dups, exp in problems:
    print(f"  [{part_str}]: total={total}, unique={unique}, dups={dups}, expected={exp}")
