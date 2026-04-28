"""Scan worker and checkpoint logs for suspicious activity that could
have produced silent undercounts.

Checks:
  - DEDUP RESUME events (the fast-forward bug marker)
  - COMBO FILE INCOMPLETE REDO events (regeneration after mismatch)
  - GAP internal errors / crashes
  - Unusual combo timing (sub-second completion on big combos)
  - BreakOnError / fatal errors
  - Missing heartbeat for long stretches
"""
import os
import re
import glob
from collections import defaultdict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"


def scan_log(path):
    findings = defaultdict(list)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return findings
    total = len(lines)
    for i, line in enumerate(lines):
        # DEDUP RESUME — pre-fix fast-forward fired
        if "DEDUP RESUME" in line:
            findings["dedup_resume"].append((i + 1, line.strip()))
        # COMBO FILE INCOMPLETE — header/line mismatch detected
        if "COMBO FILE INCOMPLETE" in line:
            findings["combo_redo"].append((i + 1, line.strip()[:120]))
        # FATAL errors
        if "FATAL" in line or "Error," in line or "Segmentation" in line:
            findings["fatal"].append((i + 1, line.strip()[:120]))
        # BreakOnError was hit (combo failed with GAP internal error)
        if "combo FAILED" in line or "BreakOnError" in line:
            findings["combo_failed"].append((i + 1, line.strip()[:120]))
        # Gasman collect failures or OOM
        if "exceeded" in line and ("memory" in line.lower() or "storage" in line.lower()):
            findings["oom"].append((i + 1, line.strip()[:120]))
    return findings


# Scan all worker stdout logs
workers_dir = BASE
logs = glob.glob(os.path.join(workers_dir, "worker_*.log"))
logs = [l for l in logs if " - Copy " not in l]
# Include checkpoint logs too
logs += glob.glob(os.path.join(BASE, "checkpoints", "*", "ckpt_18_*.log"))

summary = defaultdict(lambda: defaultdict(int))
sample = defaultdict(list)

for log in logs:
    findings = scan_log(log)
    for kind, items in findings.items():
        summary[kind][os.path.basename(log)] = len(items)
        for item in items[:2]:
            sample[kind].append((os.path.basename(log), item))

print("=" * 80)
print("LOG SCAN SUMMARY")
print("=" * 80)
for kind in ["dedup_resume", "combo_redo", "fatal", "combo_failed", "oom"]:
    per_log = summary.get(kind, {})
    total = sum(per_log.values())
    print(f"\n{kind}: {total} occurrences across {len(per_log)} files")
    if total > 0:
        for log, count in sorted(per_log.items(), key=lambda x: -x[1])[:15]:
            print(f"  {count:>4}x {log}")
        print("  Sample entries:")
        for log, (lineno, text) in sample.get(kind, [])[:6]:
            print(f"    [{log}:{lineno}] {text}")

# Separately: check for logs that contain the OLD-FORMAT DEDUP RESUME
# ("DEDUP RESUME: skipping first") — this pre-dates the code-hash check
# and was a looser version of the fast-forward bug.
print()
print("=" * 80)
print("PRE-CODE-HASH DEDUP RESUME (looser fast-forward, could have skipped valid candidates)")
print("=" * 80)
old_form = defaultdict(list)
for log in logs:
    try:
        with open(log, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if "DEDUP RESUME: skipping first" in line and "code hash" not in line:
                    old_form[os.path.basename(log)].append((i + 1, line.strip()[:100]))
    except OSError: continue

if old_form:
    print(f"\nFound old-format DEDUP RESUME in {len(old_form)} log files:")
    for log, events in sorted(old_form.items()):
        print(f"  {log}: {len(events)} event(s)")
        # Try to associate with the partition from log filename
        m = re.search(r"ckpt_18_([\d_]+)", log)
        if m:
            part_name = "[" + m.group(1).replace("_", ",") + "]"
            print(f"    -> partition {part_name}")
        else:
            # worker stdout log — partition from context
            print(f"    -> partition unknown (worker-level log)")
else:
    print("None found in .log files. (Note: we earlier found 16 in worker_269 - Copy logs,")
    print("       those are historical backups. The current main logs do not have them.)")
