"""Periodic sync from parallel_s16_m6m7/ to parallel_sn/16/ while S_16 runs.

Runs until the S_16 orchestrator writes 'FINAL:' to its master log, then does
a final sync and exits.
"""
import os, shutil, time, sys
from pathlib import Path

SRC = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7")
DST = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_sn/16")
MASTER_LOG = SRC / "run_s16_m6m7.log"

DST.mkdir(parents=True, exist_ok=True)

def sync_once():
    copied_files = 0
    for part_dir in SRC.glob("[[]*[]]"):
        name = part_dir.name
        dst_part = DST / name
        dst_part.mkdir(exist_ok=True)
        for f in part_dir.iterdir():
            if not f.is_file():
                continue
            dst_f = dst_part / f.name
            if not dst_f.exists() or dst_f.stat().st_mtime < f.stat().st_mtime:
                shutil.copy2(f, dst_f)
                copied_files += 1
    return copied_files

def final_seen():
    if not MASTER_LOG.exists():
        return False
    with open(MASTER_LOG) as f:
        return any("FINAL:" in line for line in f)

print("Starting periodic sync: parallel_s16_m6m7/ -> parallel_sn/16/")
while True:
    copied = sync_once()
    if copied > 0:
        print(f"sync: {copied} files updated")
    if final_seen():
        print("FINAL seen — doing last sync and exiting")
        sync_once()
        break
    time.sleep(60)

print("Done.")
