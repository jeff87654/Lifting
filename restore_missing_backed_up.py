"""Copy any backed-up combo file in parallel_s18_stale_sn_backup/ to current
parallel_s18/ if current is missing it. Skip if current already has the file
(worker may have regenerated it).
"""
import shutil
from pathlib import Path

STALE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18_stale_sn_backup")
CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")

restored = 0
already_present = 0
for pdir in STALE.iterdir():
    if not pdir.is_dir(): continue
    target_dir = CUR / pdir.name
    if not target_dir.is_dir(): continue
    for bf in pdir.glob("*.g"):
        target = target_dir / bf.name
        if target.is_file():
            already_present += 1
            continue
        shutil.copy2(bf, target)
        restored += 1
print(f"Restored {restored} combo files from stale_sn_backup")
print(f"Already present (worker regenerated): {already_present}")
