"""Move every affected combo file listed in affected_combos.txt to a
parallel backup directory, then delete the original. The backup preserves
partition folder structure so we can compare old vs new after re-run.
"""
import os
import shutil
import sys

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
BACKUP = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18_prebugfix_backup"
MANIFEST = r"C:\Users\jeffr\Downloads\Lifting\affected_combos.txt"

if not os.path.exists(BACKUP):
    os.makedirs(BACKUP)

moved = 0
missing = 0
errors = 0
with open(MANIFEST) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        partition, fname = parts[0], parts[1]
        src = os.path.join(BASE, partition, fname)
        if not os.path.exists(src):
            missing += 1
            continue
        dest_dir = os.path.join(BACKUP, partition)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, fname)
        try:
            shutil.move(src, dest)
            moved += 1
        except OSError as e:
            errors += 1
            print(f"ERROR: {src}: {e}", file=sys.stderr)

print(f"Moved: {moved}")
print(f"Missing (already gone): {missing}")
print(f"Errors: {errors}")
