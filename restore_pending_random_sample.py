"""Restore from random_sample_backup any combo files that are
missing or empty/invalid in parallel_s18 (the 540 pending reruns)."""
from pathlib import Path
import shutil

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
BK = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_random_sample_backup")


def has_count(p):
    try:
        with open(p, errors="replace") as f:
            for line in f:
                if line.startswith("# deduped:"):
                    return True
                if line.startswith("["):
                    return False
    except OSError:
        return False
    return False


restored = 0
already_done = 0
missing_dir = 0

for pdir in BK.iterdir():
    if not pdir.is_dir() or not pdir.name.startswith("["):
        continue
    cur_pdir = CUR / pdir.name
    if not cur_pdir.exists():
        cur_pdir.mkdir(parents=True, exist_ok=True)
        missing_dir += 1
    for bf in pdir.glob("*.g"):
        cf = cur_pdir / bf.name
        if cf.is_file() and has_count(cf):
            already_done += 1
            continue
        # Missing or empty/invalid: restore from backup
        shutil.copy2(bf, cf)
        restored += 1

print(f"Restored:    {restored}")
print(f"Already done: {already_done}")
print(f"Missing partition dirs created: {missing_dir}")
