"""Random sample 1000 combos, back them up, delete from current, launch workers.

Later, compare rerun outputs to backup: any difference = real finding.
"""
import os, random, shutil
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BACKUP = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_random_sample_backup")
CKPT = CUR / "checkpoints"

# Don't touch partitions where workers are currently running
ACTIVE = {"[6,4,4,4]", "[5,4,4,3,2]"}

random.seed(20260424)

# Collect candidate combos (existing + valid)
candidates = []
for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    if pdir.name in ACTIVE: continue
    for cf in pdir.glob("*.g"):
        candidates.append((pdir.name, cf.name))

print(f"Candidate combos (non-active partitions): {len(candidates)}")
sample_size = min(1000, len(candidates))
sample = random.sample(candidates, sample_size)
print(f"Sampled: {len(sample)}")

# Group by partition
by_part = defaultdict(list)
for p, c in sample:
    by_part[p].append(c)

print(f"Across {len(by_part)} partitions")
top = sorted(by_part.items(), key=lambda kv: -len(kv[1]))[:10]
print(f"Top 10 partitions by sample count:")
for p, combos in top:
    print(f"  {p}: {len(combos)}")

BACKUP.mkdir(exist_ok=True)

# Backup + delete
backed = 0; deleted = 0
for p, c in sample:
    src = CUR / p / c
    if not src.is_file(): continue
    dst_dir = BACKUP / p
    dst_dir.mkdir(exist_ok=True)
    shutil.copy2(src, dst_dir / c)
    backed += 1
    src.unlink()
    deleted += 1

print(f"Backed up: {backed}, deleted: {deleted}")

# Delete checkpoint files for affected partitions so workers don't replay stale state
ckpt_deleted = 0
for part in by_part:
    part_underscore = part.strip("[]").replace(",", "_")
    for wdir in CKPT.iterdir() if CKPT.is_dir() else []:
        if not wdir.is_dir(): continue
        for name in (f"ckpt_18_{part_underscore}.log",
                     f"ckpt_18_{part_underscore}.g",
                     f"ckpt_18_{part_underscore}.g.bak"):
            f = wdir / name
            if f.is_file():
                f.unlink()
                ckpt_deleted += 1

print(f"Deleted {ckpt_deleted} checkpoint files for {len(by_part)} affected partitions")
print()
print("Affected partitions (to launch workers on):")
for p in sorted(by_part):
    print(f"  {p}")
