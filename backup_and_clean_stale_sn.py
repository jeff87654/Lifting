"""Backup + delete stale S_n combo files from not-rerun partitions,
and delete their checkpoint state. Preserves active partitions
([6,4,4,4], [5,4,4,3,2]) where workers are currently running.

After this, launching workers on the cleaned partitions will re-run
only the deleted combos (existing non-S_n combos remain via
COMBO FILE EXISTS skip).
"""
import os, re, shutil
from pathlib import Path
from collections import defaultdict

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_bugfix1_backup")
BACKUP_DIR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_stale_sn_backup")
CKPT = CUR / "checkpoints"

ACTIVE = {"[6,4,4,4]", "[5,4,4,3,2]"}

SN = {5:5, 6:16, 7:7, 8:50, 9:34, 10:45}


def deduped(path):
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    try: return int(line.split(":",1)[1].strip())
                    except ValueError: return None
                if line.startswith("["):
                    return None
    except OSError:
        return None
    return None


def has_sn(cname):
    for m in re.finditer(r"\[(\d+),(\d+)\]", cname):
        d, i = int(m.group(1)), int(m.group(2))
        if d in SN and i == SN[d]: return True
    return False


BACKUP_DIR.mkdir(exist_ok=True)

# Collect all affected (partition, file) pairs
victims = []
for pdir in CUR.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["): continue
    if pdir.name in ACTIVE: continue  # skip active
    bkdir = BK / pdir.name
    if not bkdir.is_dir(): continue
    for cf in bkdir.glob("*.g"):
        curf = pdir / cf.name
        if not curf.is_file(): continue
        bc = deduped(cf); cc = deduped(curf)
        if bc is None or cc is None or bc != cc: continue
        if not has_sn(cf.name): continue
        victims.append((pdir.name, cf.name, cc))

victims_by_part = defaultdict(list)
for p, n, c in victims:
    victims_by_part[p].append((n, c))

print(f"Total suspect S_n combos: {len(victims)}")
print(f"Across {len(victims_by_part)} partitions")
print(f"Total attributed classes: {sum(v[2] for v in victims):,}")
print()

# Backup: copy suspect combo files to parallel_s18_stale_sn_backup/<partition>/
print("Backing up...")
backed = 0
for p, n, c in victims:
    src = CUR / p / n
    dst_dir = BACKUP_DIR / p
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / n
    shutil.copy2(src, dst)
    backed += 1
print(f"  Backed up {backed} files to {BACKUP_DIR}")

# Delete suspect combo files from current
deleted = 0
for p, n, _ in victims:
    src = CUR / p / n
    if src.is_file():
        src.unlink()
        deleted += 1
print(f"  Deleted {deleted} suspect combo files from current")

# Delete checkpoint files for affected partitions
ckpt_deleted = 0
for part in victims_by_part:
    part_underscore = part.strip("[]").replace(",", "_")
    for wdir in CKPT.iterdir():
        if not wdir.is_dir(): continue
        for pattern in [f"ckpt_18_{part_underscore}.log", f"ckpt_18_{part_underscore}.g",
                        f"ckpt_18_{part_underscore}.g.bak"]:
            f = wdir / pattern
            if f.is_file():
                f.unlink()
                ckpt_deleted += 1
print(f"  Deleted {ckpt_deleted} checkpoint files for affected partitions")

print()
print(f"Affected partitions (to launch workers on):")
for part in sorted(victims_by_part):
    print(f"  {part}: {len(victims_by_part[part])} S_n combos to rerun")
