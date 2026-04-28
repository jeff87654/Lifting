"""Reset S_18 manifest + result files for partitions with missing combos."""
import json, os, re, ast
from pathlib import Path
from collections import Counter
from math import comb

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
MANIFEST = BASE / "manifest.json"

TG_COUNT = {2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
            9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63,
            15: 104, 16: 1954, 17: 10, 18: 983}

def expected_combos(part):
    bc = Counter(part)
    total = 1
    for s, m in bc.items():
        total *= comb(TG_COUNT[s] + m - 1, m)
    return total

def partition_key(p):
    return "_".join(str(x) for x in p)

# Identify partitions that truly need more work
need_work = []  # list of tuples
for d in sorted(os.listdir(BASE)):
    if not d.startswith("["): continue
    dpath = BASE / d
    if not dpath.is_dir(): continue
    part = tuple(int(x) for x in d.strip("[]").split(","))
    expected = expected_combos(part)
    actual = len(list(dpath.glob("*.g")))
    has_summary = (dpath / "summary.txt").is_file()
    if actual < expected or not has_summary:
        need_work.append((part, actual, expected, has_summary))

print(f"Partitions needing work: {len(need_work)}")
total_missing_combos = sum(e - a for _, a, e, _ in need_work)
print(f"Total missing combos: {total_missing_combos}")

# Update manifest: mark these as "pending" / clear completed_at
with open(MANIFEST) as f:
    manifest = json.load(f)

for part, actual, expected, has_summary in need_work:
    key = partition_key(part)
    if key in manifest["partitions"]:
        info = manifest["partitions"][key]
        info["status"] = "pending"
        info["fpf_count"] = None
        info["elapsed_s"] = None
        info["completed_at"] = None

with open(MANIFEST, "w") as f:
    json.dump(manifest, f, indent=2)

# Scrub worker_*_results.txt: remove lines matching incomplete partitions
incomplete_set = {partition_key(p) for p, _, _, _ in need_work}
incomplete_str_set = {str(list(p)) for p, _, _, _ in need_work}

# Alternate string forms (with various spacing)
scrubbed = 0
for fpath in BASE.glob("worker_*_results.txt"):
    out_lines = []
    with open(fpath) as f:
        for line in f:
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("TOTAL") or line_strip.startswith("TIME"):
                out_lines.append(line)
                continue
            # parse "[ 5, 4, 4 ] 25" format
            parts = line_strip.rsplit(" ", 1)
            if len(parts) == 2:
                part_str = parts[0].strip()
                try:
                    p = tuple(ast.literal_eval(part_str.replace(" ", "")))
                    key = partition_key(p)
                    if key in incomplete_set:
                        scrubbed += 1
                        continue  # drop this line
                except (ValueError, SyntaxError):
                    pass
            out_lines.append(line)
    with open(fpath, "w") as f:
        f.writelines(out_lines)

print(f"Scrubbed {scrubbed} stale lines from worker_*_results.txt")

# Also remove summary.txt files for partitions that are incomplete
# (so get_completed_partitions_from_results won't misread them)
# Actually, summary.txt isn't used by that function, only gens/ and worker_*_results.txt
# But let's also delete stale gens_ files
gens_dir = BASE / "gens"
cleared = 0
if gens_dir.is_dir():
    for part, _, _, _ in need_work:
        fname = f"gens_{partition_key(part)}.txt"
        fpath = gens_dir / fname
        if fpath.is_file():
            fpath.unlink()
            cleared += 1
print(f"Removed {cleared} stale gens files")

print("\nDone. Manifest + result files scrubbed. Now run:")
print("  python run_s18.py --resume --workers 6")
