###############################################################################
# monitor_s15_verify.py - Real-time progress dashboard for S15 verification
#
# Usage:
#   python monitor_s15_verify.py                  # Default 60s refresh
#   python monitor_s15_verify.py --interval 30    # 30s refresh
#   python monitor_s15_verify.py --once           # Single snapshot, no refresh
#
###############################################################################

import os
import sys
import time
import re
import json
import argparse
import datetime
import subprocess
from collections import Counter

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s15_verify")
NUM_WORKERS = 6
EXPECTED_TOTAL = 159128  # sum of all FPF partition counts (excludes trivial group)
EXPECTED_S15_TOTAL = 159129  # including trivial group

# NrTransitiveGroups for degrees 1..15
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104,
}


def total_combos_for_partition(partition):
    """Compute total number of factor combos for a partition."""
    from math import comb
    total = 1
    for d, m in Counter(partition).items():
        n = NR_TRANSITIVE.get(d, d)
        total *= comb(n + m - 1, m)
    return total


def load_manifest():
    """Load manifest to get worker assignments and expected counts."""
    mf_path = os.path.join(OUTPUT_DIR, "manifest.json")
    if not os.path.exists(mf_path):
        return {}
    try:
        with open(mf_path) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}


def read_heartbeat(worker_id):
    """Read heartbeat file. Returns (content, mtime) or (None, None)."""
    hb_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_heartbeat.txt")
    try:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            with open(hb_file, "r") as f:
                content = f.read().strip()
            return content, mtime
    except (OSError, IOError):
        pass
    return None, None


def get_log_info(worker_id):
    """Get log file size, mtime, and last meaningful lines."""
    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log")
    if not os.path.exists(log_file):
        return None, None, []
    try:
        size = os.path.getsize(log_file)
        mtime = os.path.getmtime(log_file)
        with open(log_file, "rb") as f:
            f.seek(0, 2)
            fsize = f.tell()
            read_size = min(fsize, 16384)
            f.seek(fsize - read_size)
            data = f.read().decode("utf-8", errors="replace")
        lines = [l.rstrip() for l in data.split("\n") if l.strip()]
        return size, mtime, lines[-20:]
    except (IOError, OSError):
        return None, None, []


def read_results(worker_id):
    """Read worker results file. Returns list of (key, count, expected, ok)."""
    res_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
    results = []
    total = None
    mismatches = None
    wtime = None
    if not os.path.exists(res_file):
        return results, total, mismatches, wtime
    try:
        with open(res_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("TOTAL "):
                    total = int(line.split()[1])
                    continue
                if line.startswith("MISMATCHES "):
                    mismatches = int(line.split()[1])
                    continue
                if line.startswith("TIME "):
                    wtime = float(line.split()[1])
                    continue
                # Format: S{d} {partition} {count} expected={expected}
                m = re.match(r'(S\d+)\s+(\[[\d,]+\])\s+(\d+)\s+expected=(\d+)', line)
                if m:
                    degree_str = m.group(1)
                    part_str = m.group(2)
                    count = int(m.group(3))
                    expected = int(m.group(4))
                    ok = (count == expected)
                    key = f"{degree_str} {part_str}"
                    results.append((key, count, expected, ok))
    except (IOError, ValueError):
        pass
    return results, total, mismatches, wtime


def check_gap_processes():
    """Check which GAP processes are running and their resource usage."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='gap.exe'", "get",
             "ProcessId,UserModeTime,WorkingSetSize", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        processes = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 4 and parts[1].isdigit():
                pid = int(parts[1])
                user_time = int(parts[2]) / 10_000_000  # 100ns -> seconds
                mem_bytes = int(parts[3])
                processes[pid] = {"cpu_s": user_time, "mem_mb": mem_bytes / (1024 * 1024)}
        return processes
    except Exception:
        return {}


def map_pids_to_workers():
    """Try to map bash PIDs to worker IDs via command line scanning."""
    pid_map = {}
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='bash.exe'", "get",
             "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split(",", 2)
            if len(parts) >= 3:
                cmdline = parts[2] if len(parts) > 2 else ""
                m = re.search(r"parallel_s15_verify/worker_(\d+)\.g", cmdline)
                if m:
                    try:
                        wid = int(m.group(1))
                        bash_pid = int(parts[1])
                        pid_map[bash_pid] = wid
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass
    return pid_map


def format_ago(seconds):
    """Format a duration as a human-readable 'ago' string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        return f"{seconds/3600:.1f}h"


def format_duration(seconds):
    """Format seconds as h:mm:ss or m:ss."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}"
    else:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"


def format_mem(mb):
    """Format memory in human-readable form."""
    if mb >= 1024:
        return f"{mb/1024:.1f}GB"
    return f"{mb:.0f}MB"


def get_worker_partition_count(manifest, wid):
    """Count how many partitions are assigned to a worker."""
    count = 0
    for key, info in manifest.items():
        if info.get('worker') == wid:
            count += 1
    return count


def display_dashboard():
    """Display the monitoring dashboard."""
    now = datetime.datetime.now()
    now_ts = time.time()

    os.system("cls" if os.name == "nt" else "clear")

    print(f"{'=' * 95}")
    print(f"  S15 Verification Monitor  |  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 95}")

    manifest = load_manifest()

    # Aggregate results across all workers
    all_results = []
    worker_summaries = {}
    all_done_workers = 0

    for wid in range(NUM_WORKERS):
        results, total, mismatches, wtime = read_results(wid)
        n_assigned = get_worker_partition_count(manifest, wid)
        n_ok = sum(1 for _, _, _, ok in results if ok)
        n_fail = sum(1 for _, _, _, ok in results if not ok)
        n_done = len(results)
        done = (total is not None)
        if done:
            all_done_workers += 1
        worker_summaries[wid] = {
            'n_assigned': n_assigned,
            'n_done': n_done,
            'n_ok': n_ok,
            'n_fail': n_fail,
            'total': total,
            'mismatches': mismatches,
            'time': wtime,
            'done': done,
        }
        all_results.extend(results)

    total_verified = len(all_results)
    total_ok = sum(1 for _, _, _, ok in all_results if ok)
    total_fail = sum(1 for _, _, _, ok in all_results if not ok)
    total_classes = sum(c for _, c, _, _ in all_results)

    # By-degree summary
    by_degree = {}
    for key, count, expected, ok in all_results:
        m = re.match(r'S(\d+)', key)
        if m:
            d = int(m.group(1))
            by_degree.setdefault(d, {'done': 0, 'ok': 0, 'fail': 0, 'classes': 0})
            by_degree[d]['done'] += 1
            by_degree[d]['classes'] += count
            if ok:
                by_degree[d]['ok'] += 1
            else:
                by_degree[d]['fail'] += 1

    # Overall progress
    status_icon = "OK" if total_fail == 0 else f"!! {total_fail} MISMATCH"
    print(f"\n  Progress: {total_verified}/175 partitions verified  [{status_icon}]")
    print(f"  Classes:  {total_classes:,} / {EXPECTED_TOTAL:,} expected")
    if total_fail > 0:
        print(f"  *** {total_fail} MISMATCHES DETECTED ***")

    # GAP processes
    gap_procs = check_gap_processes()
    total_mem_gb = sum(p['mem_mb'] for p in gap_procs.values()) / 1024
    active_gaps = len(gap_procs)
    print(f"  GAP procs: {active_gaps} running ({total_mem_gb:.1f}GB total)")

    # Degree progress table
    print(f"\n  {'Degree':>6} {'Done':>6} {'OK':>5} {'Fail':>5} {'Classes':>8}")
    print(f"  {'-'*6} {'-'*6} {'-'*5} {'-'*5} {'-'*8}")

    # Expected partitions per degree (from the dry run output)
    expected_per_degree = {
        2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 7, 9: 8,
        10: 12, 11: 14, 12: 21, 13: 24, 14: 34, 15: 41
    }

    for d in range(2, 16):
        info = by_degree.get(d, {'done': 0, 'ok': 0, 'fail': 0, 'classes': 0})
        exp_n = expected_per_degree.get(d, 0)
        fail_str = str(info['fail']) if info['fail'] > 0 else "."
        done_str = f"{info['done']}/{exp_n}"
        check = "  *" if info['fail'] > 0 else ("  v" if info['done'] == exp_n else "")
        print(f"  S{d:>4} {done_str:>6} {info['ok']:>5} {fail_str:>5} {info['classes']:>8}{check}")

    # Worker status table
    print(f"\n  {'Worker':>6} {'Done':>8} {'OK':>5} {'Fail':>5} {'Status':>10} "
          f"{'HB age':>7} {'Mem':>7} {'Current partition'}")
    print(f"  {'-'*6} {'-'*8} {'-'*5} {'-'*5} {'-'*10} "
          f"{'-'*7} {'-'*7} {'-'*30}")

    for wid in range(NUM_WORKERS):
        ws = worker_summaries[wid]
        hb_content, hb_mtime = read_heartbeat(wid)
        log_size, log_mtime, log_lines = get_log_info(wid)

        # Status
        if ws['done']:
            status = "DONE"
        elif hb_mtime is not None:
            staleness = now_ts - hb_mtime
            recently_active = staleness < 1800
            if log_mtime and (now_ts - log_mtime) < 1800:
                recently_active = True
            if recently_active:
                status = "RUNNING"
            else:
                status = "STALE"
        elif log_mtime and (now_ts - log_mtime) < 1800:
            status = "STARTING"
        else:
            status = "UNKNOWN"

        if ws['n_fail'] > 0 and status != "DONE":
            status = f"ERR({ws['n_fail']})"

        # HB age
        hb_age_str = "-"
        if hb_mtime:
            hb_age_str = format_ago(now_ts - hb_mtime)

        # Memory: find the largest gap.exe process not yet claimed
        mem_str = "-"
        # Simple approach: sort gap procs by memory, assign to workers in order
        # (imperfect but gives an overview)
        sorted_procs = sorted(gap_procs.values(), key=lambda x: -x['mem_mb'])
        if wid < len(sorted_procs):
            mem_str = format_mem(sorted_procs[wid]['mem_mb'])

        # Current partition from heartbeat
        current = "-"
        if hb_content:
            if "done" in hb_content or "completed" in hb_content:
                # Extract last completed partition
                m = re.search(r'done (S\d+ \[[\d,]+\])', hb_content)
                if m:
                    current = f"{m.group(1)} (done)"
                else:
                    current = hb_content[:40]
            elif "starting" in hb_content:
                m = re.search(r'starting (S\d+ partition \[[\d,]+\])', hb_content)
                if m:
                    current = m.group(1)
                else:
                    current = hb_content[:40]
            elif "combo" in hb_content:
                # Mid-computation heartbeat
                m = re.search(r'combo #(\d+)', hb_content)
                fpf_m = re.search(r'fpf=(\d+)', hb_content)
                if m:
                    combo = m.group(1)
                    fpf = fpf_m.group(1) if fpf_m else "?"
                    current = f"combo #{combo} fpf={fpf}"
                else:
                    current = hb_content[:40]
            else:
                current = hb_content[:40]

        done_str = f"{ws['n_done']}/{ws['n_assigned']}"
        fail_str = str(ws['n_fail']) if ws['n_fail'] > 0 else "."

        # Time for completed workers
        time_str = ""
        if ws['done'] and ws['time'] is not None:
            time_str = f" [{format_duration(ws['time'])}]"

        print(f"  W{wid:>4} {done_str:>8} {ws['n_ok']:>5} {fail_str:>5} {status:>10} "
              f"{hb_age_str:>7} {mem_str:>7} {current}{time_str}")

    # Mismatches detail
    mismatches = [(key, count, expected) for key, count, expected, ok in all_results if not ok]
    if mismatches:
        print(f"\n  === MISMATCHES ({len(mismatches)}) ===")
        for key, count, expected in sorted(mismatches):
            diff = count - expected
            sign = "+" if diff > 0 else ""
            print(f"    {key:25s}  got {count:>6}  expected {expected:>6}  ({sign}{diff})")

    # Log tails for active workers
    skip_patterns = [
        "Syntax warning", "Unbound global", "loaded.", "===============",
        "Functions:", "Config:", "Main:", "Test:", "Stats:", "Wrapper:",
        "Caching:", "Precomputed:", "Debugging:", "Uses:", "Loaded LIFT_CACHE",
        "Database loaded", "images package", "Database loader",
        "Call LoadDatabase", "Loaded elementary", "Loaded transitive",
        "Loaded ", "Loading precomputed", "Worker ", "H^1 Orbital module",
        "Cohomology module", "Modules loaded", "Lifting Algorithm loaded",
        "Lifting Method FAST", "Processing ", "Verifying ",
    ]

    active_workers = [wid for wid in range(NUM_WORKERS) if not worker_summaries[wid]['done']]
    if active_workers:
        print(f"\n  --- Active Worker Logs ---")
        for wid in active_workers:
            _, _, log_lines = get_log_info(wid)
            if not log_lines:
                continue
            meaningful = [l for l in log_lines
                          if l.strip()
                          and not l.strip().startswith("^")
                          and not any(p in l for p in skip_patterns)]
            if meaningful:
                print(f"\n  W{wid}:")
                for line in meaningful[-3:]:
                    display = line.strip()[:100]
                    if display:
                        print(f"    {display}")

    # Final summary when all workers done
    if all_done_workers == NUM_WORKERS:
        print(f"\n  {'=' * 50}")
        print(f"  ALL WORKERS COMPLETE")
        total_time = max(ws['time'] or 0 for ws in worker_summaries.values())
        print(f"  Wall time: {format_duration(total_time)}")
        print(f"  Total classes: {total_classes:,}")
        print(f"  Expected:      {EXPECTED_TOTAL:,}")
        if total_classes == EXPECTED_TOTAL:
            print(f"  RESULT: PASS (all {total_verified} partitions match)")
        else:
            print(f"  RESULT: FAIL ({total_fail} mismatches, "
                  f"diff={total_classes - EXPECTED_TOTAL:+d})")
        print(f"  {'=' * 50}")

    print(f"\n{'=' * 95}")


def main():
    parser = argparse.ArgumentParser(description="Monitor S15 verification progress")
    parser.add_argument("--interval", type=int, default=60,
                       help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true",
                       help="Display once and exit")
    args = parser.parse_args()

    if args.once:
        display_dashboard()
        return

    print("Starting S15 verification monitor (Ctrl+C to stop)...")
    try:
        while True:
            display_dashboard()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
