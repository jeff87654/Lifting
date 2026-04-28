###############################################################################
# monitor_s17.py - Progress dashboard for S17 computation
#
# Detects active workers by log-file freshness (works with any launch method).
# Groups display by partition, not worker ID.
#
# Usage:
#   python monitor_s17.py                  # Default 60s refresh
#   python monitor_s17.py --interval 30    # 30s refresh
#   python monitor_s17.py --once           # Single snapshot
#
###############################################################################

import os
import sys
import time
import re
import glob
import argparse
import datetime
import subprocess
from collections import Counter

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s17")
N = 17
INHERITED = 686165        # OEIS A000638(16)
EXPECTED_FPF = 780193     # FPF classes for S17
OEIS_S17 = INHERITED + EXPECTED_FPF  # = 1,466,358
TOTAL_PARTITIONS = 66

# Corrected counts for partitions with checkpoint-inflated results
# (original counts were 2x-3x due to non-atomic checkpoint save/restore)
CORRECTED_COUNTS = {
    (6, 5, 4, 2): 26826,
    (8, 5, 4): 33260,
    (6, 4, 3, 2, 2): 59732,
}

NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954, 17: 5,
}


def partitions_no_ones(n, max_part=None):
    if max_part is None:
        max_part = n
    if n == 0:
        return [()]
    result = []
    for i in range(min(n, max_part), 1, -1):
        for rest in partitions_no_ones(n - i, i):
            result.append((i,) + rest)
    return result


def total_combos(partition):
    t = 1
    for d in partition:
        t *= NR_TRANSITIVE[d]
    return t


def get_completed_partitions():
    """Parse results files to find completed partitions.
    Applies corrections for checkpoint-inflated partitions."""
    completed = {}
    for fn in glob.glob(os.path.join(OUTPUT_DIR, "worker_*_results.txt")):
        with open(fn) as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    parts_str, count_str = line.rsplit("]", 1)
                    parts = tuple(
                        int(x) for x in parts_str.strip("[ ").replace(" ", "").split(",")
                    )
                    count = int(count_str.strip())
                    completed[parts] = count

    # Apply corrected counts for checkpoint-inflated partitions
    for parts, corrected in CORRECTED_COUNTS.items():
        if parts in completed:
            completed[parts] = corrected

    return completed


def find_best_checkpoint(partition):
    """Find the best checkpoint combo count for a partition across all workers.
    Reads both .g base checkpoint and .log deltas (handles deduped checkpoints).
    Prefers the most recently modified checkpoint to avoid stale inflated data."""
    part_str = "_".join(str(x) for x in partition)
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    if not os.path.exists(ckpt_base):
        return 0, 0

    candidates = []
    for entry in os.listdir(ckpt_base):
        worker_dir = os.path.join(ckpt_base, entry)
        if not os.path.isdir(worker_dir):
            continue

        g_file = os.path.join(worker_dir, f"ckpt_17_{part_str}.g")
        log_file = os.path.join(worker_dir, f"ckpt_17_{part_str}.log")

        if not os.path.exists(g_file) and not os.path.exists(log_file):
            continue

        # Use freshest modification time across .g and .log
        mtime = 0
        if os.path.exists(g_file):
            mtime = max(mtime, os.path.getmtime(g_file))
        if os.path.exists(log_file):
            mtime = max(mtime, os.path.getmtime(log_file))

        base_combos = 0
        base_fpf = 0
        log_combos = 0
        log_fpf = 0

        # Parse .g base checkpoint (read first 512KB for header/counts)
        if os.path.exists(g_file):
            try:
                with open(g_file, "r", errors="replace") as f:
                    head = f.read(512 * 1024)
                # Try comment header (written by dedup_checkpoints.py)
                m = re.search(r"# (\d+) combos, (\d+) groups", head)
                if m:
                    base_combos = int(m.group(1))
                    base_fpf = int(m.group(2))
                else:
                    # Parse _CKPT_ADDED_COUNT
                    m = re.search(r"_CKPT_ADDED_COUNT\s*:=\s*(\d+)", head)
                    if m:
                        base_fpf = int(m.group(1))
                    # Count keys in _CKPT_COMPLETED_KEYS := [ ... ];
                    ks = head.find("_CKPT_COMPLETED_KEYS := [")
                    if ks >= 0:
                        ke = head.find("];", ks)
                        if ke > 0:
                            base_combos = head[ks:ke].count('"') // 2
            except (OSError, IOError):
                pass

        # Parse .log deltas (combos since last full .g save)
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", errors="replace") as f:
                    for line in f:
                        if line.startswith("# end combo"):
                            log_combos += 1
                            m = re.search(r"\((\d+) total fpf\)", line)
                            if m:
                                log_fpf = int(m.group(1))
            except (OSError, IOError):
                pass

        combos = base_combos + log_combos
        # .log fpf is running total (overrides base); use base if no .log entries
        fpf = log_fpf if log_fpf > 0 else base_fpf

        candidates.append((mtime, combos, fpf))

    if not candidates:
        return 0, 0

    # Pick the most recently modified checkpoint (avoids stale inflated data)
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1], candidates[0][2]


def get_worker_partition(worker_id):
    """Read the .g script to find which partition a worker is computing."""
    script = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.g")
    if not os.path.exists(script):
        return None
    with open(script) as f:
        for line in f:
            if "FindFPFClassesForPartition" in line:
                m = re.search(r"\[[\d,]+\]", line)
                if m:
                    return tuple(int(x) for x in m.group().strip("[]").split(","))
    return None


def find_active_workers(completed):
    """Find workers that are likely still running, grouped by partition.

    A worker is considered active if ANY of these are fresh (< 1 hour):
      - log file modification time
      - heartbeat file modification time
      - checkpoint file modification time

    Returns dict: partition -> (wid, freshest_age, heartbeat_detail)
    Only the most recent worker per partition is kept.
    """
    active = {}
    now = time.time()
    max_age = 3600  # 1 hour threshold

    for fn in glob.glob(os.path.join(OUTPUT_DIR, "worker_*.log")):
        wid_str = os.path.basename(fn).replace("worker_", "").replace(".log", "")
        try:
            wid = int(wid_str)
        except ValueError:
            continue
        partition = get_worker_partition(wid)
        if partition is None or partition in completed:
            continue

        # Check freshest timestamp across log, heartbeat, and checkpoint
        ages = []
        log_age = now - os.path.getmtime(fn)
        ages.append(log_age)

        hb_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
        if os.path.exists(hb_file):
            ages.append(now - os.path.getmtime(hb_file))

        part_str = "_".join(str(x) for x in partition)
        ckpt_file = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}",
                                 f"ckpt_17_{part_str}.log")
        if os.path.exists(ckpt_file):
            ages.append(now - os.path.getmtime(ckpt_file))

        freshest = min(ages)
        if freshest > max_age:
            continue

        # Read heartbeat for combo/fpf detail
        hb_detail = ""
        if os.path.exists(hb_file):
            with open(hb_file) as f:
                hb_detail = f.read().strip()

        if partition not in active or wid > active[partition][0]:
            active[partition] = (wid, freshest, hb_detail)

    return active


def get_gap_memory():
    """Get total memory used by gap.exe processes and count."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq gap.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        total_kb = 0
        count = 0
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or "gap.exe" not in line:
                continue
            count += 1
            m = re.search(r'"([\d,]+) K"', line)
            if m:
                total_kb += int(m.group(1).replace(",", ""))
        return count, total_kb / 1024 / 1024  # count, GB
    except Exception:
        return 0, 0


def format_time(seconds):
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h{m:02d}m"
    elif seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m{s:02d}s"
    return f"{seconds:.0f}s"


def make_bar(fraction, width=30):
    filled = int(width * min(fraction, 1.0))
    return "#" * filled + "-" * (width - filled)


def display_dashboard():
    now = datetime.datetime.now()
    os.system("cls" if os.name == "nt" else "clear")

    completed = get_completed_partitions()
    all_parts = partitions_no_ones(17)
    missing = [p for p in all_parts if p not in completed]

    total_fpf_completed = sum(completed.values())

    # Add in-progress FPF from checkpoint files for incomplete partitions
    in_progress_fpf = 0
    for p in missing:
        _, fpf = find_best_checkpoint(p)
        in_progress_fpf += fpf

    total_fpf = total_fpf_completed + in_progress_fpf
    total_s17 = INHERITED + total_fpf
    pct_fpf = total_fpf / EXPECTED_FPF * 100
    pct_parts = len(completed) / TOTAL_PARTITIONS * 100

    gap_count, gap_gb = get_gap_memory()

    # Header
    print(f"  S17 Computation Monitor  |  {now.strftime('%H:%M:%S')}  |  "
          f"{gap_count} GAP processes ({gap_gb:.1f} GB)")
    print(f"  {'=' * 72}")
    print(f"  Partitions:  {len(completed)}/{TOTAL_PARTITIONS} ({pct_parts:.0f}%)    "
          f"FPF: {total_fpf:,}/{EXPECTED_FPF:,} ({pct_fpf:.1f}%)")
    print(f"  Total: {total_s17:,}/{OEIS_S17:,}    "
          f"(completed: {total_fpf_completed:,} + in-progress: {in_progress_fpf:,})")
    print(f"  [{make_bar(len(completed) / TOTAL_PARTITIONS)}] partitions")
    print(f"  [{make_bar(total_fpf / EXPECTED_FPF)}] FPF classes")

    # Active workers (grouped by partition)
    active = find_active_workers(completed)

    if active:
        print(f"\n  Active ({len(active)}):")
        print(f"  {'Partition':25s} {'Progress':>12}   {'%':>5}  {'FPF':>7}  {'Worker':>6}  {'Last':>7}  Detail")
        print(f"  {'-'*25} {'-'*12}   {'-'*5}  {'-'*7}  {'-'*6}  {'-'*7}  {'-'*20}")
        for p in sorted(active.keys()):
            wid, freshest_age, hb_detail = active[p]
            ckpt, fpf = find_best_checkpoint(p)
            tc = total_combos(p)
            pct = ckpt * 100 / tc if tc > 0 else 0
            age_str = format_time(freshest_age)
            # Extract detail from heartbeat
            detail = ""
            if "combo #" in hb_detail:
                m = re.search(r"combo #(\d+) fpf=(\d+)", hb_detail)
                if m:
                    detail = f"combo #{m.group(1)}, fpf={m.group(2)}"
            elif "completed" in hb_detail:
                detail = "finishing..."
            elif "starting" in hb_detail:
                detail = "loading..."
            elif "restoring" in hb_detail.lower() or "recomput" in hb_detail.lower():
                detail = "restoring checkpoint..."
            print(f"  {str(list(p)):25s} {ckpt:>5}/{tc:<5}   {pct:4.0f}%  {fpf:>7,}  W{wid:>4}  {age_str:>7}  {detail}")

    # Waiting partitions (no active worker)
    waiting = [p for p in missing if p not in active]
    if waiting:
        print(f"\n  Waiting ({len(waiting)}, no active worker):")
        print(f"  {'Partition':25s} {'Progress':>12}   {'%':>5}  {'FPF':>7}")
        print(f"  {'-'*25} {'-'*12}   {'-'*5}  {'-'*7}")
        for p in sorted(waiting, key=lambda p: -find_best_checkpoint(p)[0] / max(total_combos(p), 1)):
            ckpt, fpf = find_best_checkpoint(p)
            tc = total_combos(p)
            pct = ckpt * 100 / tc if tc > 0 else 0
            print(f"  {str(list(p)):25s} {ckpt:>5}/{tc:<5}   {pct:4.0f}%  {fpf:>7,}")

    # Recently completed (last 10, sorted by FPF count)
    if completed:
        top = sorted(completed.items(), key=lambda x: -x[1])[:10]
        print(f"\n  Top 10 completed:")
        for p, count in top:
            print(f"  {str(list(p)):25s} {count:>7,}")

    print(f"\n  {'=' * 72}")


def main():
    parser = argparse.ArgumentParser(description="Monitor S17 computation")
    parser.add_argument("--interval", type=int, default=60,
                        help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true",
                        help="Display once and exit")
    args = parser.parse_args()

    if args.once:
        display_dashboard()
        return

    print("Starting S17 monitor (Ctrl+C to stop)...")
    try:
        while True:
            display_dashboard()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
