"""Per-combo comparison for one partition:
  - sum all partial-dedup blocks per combo per log (cumulative within a run)
  - per combo, take MAX across workers/logs (one session produced this much)
  - compare to combo file's # deduped
"""
import os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
CKPT = BASE / "checkpoints"

part_str = sys.argv[1] if len(sys.argv) > 1 else "[6,6,3,3]"
part_underscore = part_str.strip("[]").replace(",", "_")
pdir = BASE / part_str


def parse_log_blocks(path):
    """Per log: cacheKey -> group count from last delta block.

    '# combo: <cacheKey>' marks start of a full-combo delta (completed combos).
    Partial-dedup checkpoints use synthetic keys like '_dedup_partial_N'.
    When a combo appears multiple times in the same log (STALE CHECKPOINT REDO
    appended to same log file), take the latest occurrence — they represent
    re-runs of the same combo, not additive work.
    """
    combos = {}  # cacheKey -> LAST observed group count
    current_key = None
    current_count = 0
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# combo:"):
                    current_key = line[8:].strip()
                    current_count = 0
                elif current_key and line.startswith("Add(_CKPT_ALL_FPF_GENS,"):
                    current_count += 1
                elif line.startswith("# end combo"):
                    if current_key is not None:
                        combos[current_key] = current_count  # overwrite prior
                    current_key = None
                    current_count = 0
    except OSError:
        pass
    return combos


# Collect max-per-combo across all worker logs for this partition
max_ckpt = defaultdict(int)
for wdir in CKPT.iterdir():
    if not wdir.is_dir(): continue
    logf = wdir / f"ckpt_18_{part_underscore}.log"
    if not logf.is_file(): continue
    combos = parse_log_blocks(logf)
    for ck, cnt in combos.items():
        if cnt > max_ckpt[ck]:
            max_ckpt[ck] = cnt


# Combo file counts
combo_file_counts = {}
for cf in pdir.glob("*.g"):
    cacheKey = None
    deduped = None
    try:
        with open(cf, errors="replace") as f:
            for line in f:
                if line.startswith("# combo:"):
                    cacheKey = line[8:].strip()
                elif line.startswith("# deduped:"):
                    deduped = int(line.split(":",1)[1].strip())
                elif line.startswith("["):
                    break
    except OSError:
        continue
    if cacheKey is not None and deduped is not None:
        combo_file_counts[cacheKey] = deduped


# Compare
print(f"Partition {part_str}")
print(f"  {len(max_ckpt)} combos in checkpoint logs")
print(f"  {len(combo_file_counts)} combos in combo files")
print()

mismatches = []
skipped_partial = 0
for ck, ckpt_n in max_ckpt.items():
    # Skip synthetic partial-dedup keys (intermediate checkpoints, not real combos)
    if ck.startswith("_dedup_partial_"):
        skipped_partial += 1
        continue
    file_n = combo_file_counts.get(ck, 0)
    if ckpt_n > file_n:
        mismatches.append((ck, file_n, ckpt_n, ckpt_n - file_n))
print(f"  (skipped {skipped_partial} synthetic _dedup_partial_* keys)")

mismatches.sort(key=lambda x: -x[3])
print(f"Combos where ckpt > file: {len(mismatches)}")
print(f"Sum of ckpt-file diff: {sum(m[3] for m in mismatches)}")
print()
if mismatches:
    print("Top mismatches (combo: file_count, ckpt_count, diff):")
    for ck, fn, cn, d in mismatches[:20]:
        print(f"  {ck}")
        print(f"    file={fn}, ckpt={cn}, diff=+{d}")
