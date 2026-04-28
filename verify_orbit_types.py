"""
Verify FPF orbit type counts match source gens file group counts.
Each gens_X_Y_Z.txt should have exactly as many groups as the [X,Y,Z] orbit type count.
"""
import os
import glob

GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"
COUNTS_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_orbit_type_counts.txt"

# Parse orbit type counts file
orbit_counts = {}
with open(COUNTS_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if line.startswith("#") or line.startswith("-") or not line:
            continue
        if line.startswith("TOTAL"):
            continue
        if line.startswith("["):
            bracket_end = line.index("]")
            label = line[:bracket_end+1]
            count = int(line[bracket_end+1:].strip())
            # Parse partition
            parts = tuple(int(x) for x in label[1:-1].split(","))
            orbit_counts[parts] = count

# Count groups in each gens file
gens_files = sorted(glob.glob(os.path.join(GENS_DIR, "gens_*.txt")))
gens_files = [f for f in gens_files if not f.endswith(".bak")]

all_ok = True
fpf_total_gens = 0
fpf_total_counts = 0

for gf in gens_files:
    fname = os.path.basename(gf)
    # Parse partition from filename: gens_8_4_3_2.txt -> (8,4,3,2)
    stem = fname.replace("gens_", "").replace(".txt", "")
    parts = tuple(int(x) for x in stem.split("_"))

    # Count groups (logical lines after joining continuations)
    count = 0
    with open(gf, "r") as f:
        buf = ""
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if line.endswith("\\"):
                buf += line[:-1]
            else:
                buf += line
                if buf.strip() and buf.strip()[0] == "[":
                    count += 1
                buf = ""

    fpf_total_gens += count
    expected = orbit_counts.get(parts, None)
    if expected is None:
        print(f"  MISSING: {parts} not found in orbit type counts! (gens has {count})")
        all_ok = False
    elif expected != count:
        print(f"  MISMATCH: {parts}: gens={count}, orbit_counts={expected}")
        all_ok = False
    else:
        print(f"  OK: {str(list(parts)):<30s} gens={count:>7d}  orbit_counts={expected:>7d}")
    if expected is not None:
        fpf_total_counts += expected

# Check for FPF orbit types not covered by any gens file
gens_partitions = set()
for gf in gens_files:
    fname = os.path.basename(gf)
    stem = fname.replace("gens_", "").replace(".txt", "")
    gens_partitions.add(tuple(int(x) for x in stem.split("_")))

fpf_orbit_types = {p: c for p, c in orbit_counts.items() if 1 not in p}
for p in sorted(fpf_orbit_types):
    if p not in gens_partitions:
        print(f"  EXTRA orbit type with no gens file: {list(p)} = {fpf_orbit_types[p]}")
        all_ok = False

print(f"\nFPF gens total:   {fpf_total_gens}")
print(f"FPF counts total: {fpf_total_counts}")
print(f"FPF orbit types:  {len(fpf_orbit_types)} (no 1s)")
print(f"Gens files:       {len(gens_files)}")
if all_ok:
    print("ALL MATCH")
else:
    print("SOME MISMATCHES - see above")
