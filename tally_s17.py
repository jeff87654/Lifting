"""Tally S17 FPF totals from gens files (deduped counts)."""
import os
import re

GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"
RESULTS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17"

# Count groups in each gens file (1 group per line after dedup)
gens_counts = {}
for f in sorted(os.listdir(GENS_DIR)):
    if not f.startswith("gens_") or not f.endswith(".txt"):
        continue
    if f.endswith(".bak"):
        continue
    part_str = f[5:-4]
    filepath = os.path.join(GENS_DIR, f)

    # Count lines (each line = 1 group, no more line continuations after dedup for fixed files)
    # But GAP-written files still have continuations. Need to count properly.
    count = 0
    buf = ""
    with open(filepath, 'r', errors='replace') as rf:
        for line in rf:
            line = line.rstrip('\n')
            if line.endswith('\\'):
                buf += line[:-1]
            else:
                buf += line
                if buf.strip() and len(buf.strip()) > 2:
                    count += 1
                buf = ""
    gens_counts[part_str] = count

# Get result counts from worker results files
result_counts = {}
for f in os.listdir(RESULTS_DIR):
    if f.startswith("worker_") and f.endswith("_results.txt"):
        fpath = os.path.join(RESULTS_DIR, f)
        try:
            with open(fpath, 'r') as rf:
                for line in rf:
                    line = line.strip()
                    if not line or line.startswith("TOTAL") or line.startswith("TIME"):
                        continue
                    m = re.match(r'\[([^\]]+)\]\s+(\d+)', line)
                    if m:
                        parts = m.group(1).replace(' ', '').replace(',', '_')
                        count = int(m.group(2))
                        result_counts[parts] = count
        except:
            pass

# Fixed counts (deduped)
fixed = {"6_5_4_2": 26826, "8_5_4": 33260, "6_4_3_2_2": 59732}

# Show all partitions
total_fpf = 0
missing = []
print(f"{'Partition':<25} {'Gens':>8} {'Results':>8} {'Status'}")
print("-" * 60)
for part_str in sorted(gens_counts.keys()):
    gc = gens_counts[part_str]
    rc = result_counts.get(part_str, "?")

    if part_str in fixed:
        status = f"FIXED (was {rc})"
        gc = fixed[part_str]
    elif gc == rc:
        status = "OK"
    else:
        status = f"MISMATCH"

    total_fpf += gc
    print(f"  [{part_str}]{'':>{22-len(part_str)}} {gc:>8} {str(rc):>8}  {status}")

print("-" * 60)
print(f"  Total FPF from {len(gens_counts)} partitions: {total_fpf}")

# Check remaining partitions
remaining = ["8_6_3", "8_4_3_2", "6_4_4_3"]
print(f"\n  Still computing: {remaining}")

S16_TOTAL = 686165
OEIS_S17 = 1466358  # Wait, 780193 is the FPF count, not total
print(f"\n  S16 inherited: {S16_TOTAL}")
print(f"  Expected FPF (OEIS): 780193")
print(f"  Expected total S17: {S16_TOTAL + 780193} = {S16_TOTAL + 780193}")
print(f"  Current FPF: {total_fpf}")
print(f"  Remaining needed: {780193 - total_fpf}")
