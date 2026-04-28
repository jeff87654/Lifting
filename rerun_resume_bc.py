"""
Resume launch of just Workers B and C (A and D done).
Skips combos that already have valid # deduped: lines on disk.
"""
import os, subprocess, sys
import rerun_82_combos as r

LOGDIR = r.LOGDIR
ROOT = r.ROOT
os.makedirs(LOGDIR, exist_ok=True)

by_part = r.parse_rerun_list()
by_part["[6,6,6]"].append([[6,16],[6,16],[6,16]])

# Only relaunch B and C
WORKER_PART = {"B": "[8,5,5]", "C": "[6,6,6]"}

procs = []
for worker_id, part_str in WORKER_PART.items():
    combos = by_part[part_str]
    g_file, log_file = r.make_worker_g(worker_id, part_str, combos)
    print(f"Launching worker {worker_id}: {part_str} ({len(combos)} combos, will skip existing)")
    proc, sout, serr = r.launch(g_file, worker_id)
    procs.append((worker_id, proc))
    print(f"  pid: {proc.pid}")

print("\nB and C launched in resume mode.")
