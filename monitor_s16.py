###############################################################################
# monitor_s16.py - Real-time progress dashboard for S16 computation
#
# Usage:
#   python monitor_s16.py                  # Default 60s refresh
#   python monitor_s16.py --interval 30    # 30s refresh
#   python monitor_s16.py --once           # Single snapshot, no refresh
#
###############################################################################

import os
import sys
import time
import re
import argparse
import datetime
import subprocess
from collections import Counter

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16
INHERITED = 159129  # S15 count

# Current worker assignments
# R16: Goursat's Lemma + CCS fast path for 2-factor/small non-abelian combos
WORKER_INFO = {
    100: {"partitions": ["[8,8]"], "round": "R16", "pid": None,
          "note": "Goursat opt, resume 840 combos, 13023 groups"},
    101: {"partitions": ["[8,4,4]"], "round": "R16", "pid": None,
          "note": "Goursat opt, resume 320 combos, 33064 groups"},
    102: {"partitions": ["[4,4,4,4]"], "round": "R16", "pid": None,
          "note": "Goursat opt, resume 39 combos, 8397 groups"},
    103: {"partitions": ["[4,4,2,2,2,2]"], "round": "R16", "pid": None,
          "note": "Goursat opt, resume 9 combos, 6932 groups"},
}

# NrTransitiveGroups for degrees 1..16
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954,
}


def total_combos_for_partition(partition):
    """Compute total number of factor combos for a partition."""
    from math import comb
    total = 1
    for d, m in Counter(partition).items():
        n = NR_TRANSITIVE.get(d, d)
        total *= comb(n + m - 1, m)
    return total


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
        return size, mtime, lines[-15:]
    except (IOError, OSError):
        return None, None, []


def get_completed_partitions():
    """Get all completed partitions from ALL worker result files."""
    results = {}  # part_key -> (count, worker_id)
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith("_results.txt") and f.startswith("worker_"):
            wid = int(f.replace("worker_", "").replace("_results.txt", ""))
            try:
                with open(os.path.join(OUTPUT_DIR, f)) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("TIME") or line.startswith("TOTAL"):
                            continue
                        if ":" in line:
                            part_str = line.split(":")[0].strip()
                            rest = line.split(":")[1].strip()
                            count = int(rest.split()[0])
                        else:
                            parts = line.rsplit(" ", 1)
                            part_str = parts[0].strip()
                            count = int(parts[1])
                        key = part_str.replace("[", "").replace("]", "").replace(" ", "").replace(",", "_")
                        if key not in results or count > results[key][0]:
                            results[key] = (count, wid)
            except (IOError, ValueError):
                pass
    return results


def check_gap_processes():
    """Check which GAP PIDs are running and their resource usage."""
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
                # CSV: Node,ProcessId,UserModeTime,WorkingSetSize
                pid = int(parts[1])
                user_time = int(parts[2]) / 10_000_000  # 100ns -> seconds
                mem_bytes = int(parts[3])
                processes[pid] = {"cpu_s": user_time, "mem_mb": mem_bytes / (1024 * 1024)}
        return processes
    except Exception:
        return {}


def parse_log_for_status(lines):
    """Extract status information from log lines."""
    info = {
        "current_combo": None,
        "combo_num": None,
        "fpf_total": None,
        "elapsed": None,
        "gf2_dedup": False,
        "ccs_active": False,
        "failed_combos": 0,
        "allsubgroups": False,
        "last_layer": None,
        "bfs_progress": None,
    }

    for line in lines:
        m = re.search(r"combo #(\d+) done \((\d+\.?\d*)s elapsed, (\d+) fpf total\)", line)
        if m:
            info["combo_num"] = int(m.group(1))
            info["elapsed"] = float(m.group(2))
            info["fpf_total"] = int(m.group(3))

        m = re.search(r">> combo \[\[ (.+?) \]\]", line)
        if m:
            info["current_combo"] = f"[[{m.group(1).replace(' ', '')}]]"

        if "GF(2) orbit dedup" in line or "GF(" in line:
            info["gf2_dedup"] = True

        if "CCS fast path" in line:
            info["ccs_active"] = True

        if "CCS dedup:" in line:
            info["ccs_active"] = True

        if "combo FAILED" in line:
            info["failed_combos"] += 1

        if "AllSubgroups" in line or "417199" in line:
            info["allsubgroups"] = True

        m = re.search(r"LiftThroughLayer \[(.+?)\] (\d+)ms", line)
        if m:
            info["last_layer"] = f"{m.group(1)} ({int(m.group(2))/1000:.0f}s)"

        m = re.search(r"BFS progress: (\d+)/(\d+)", line)
        if m:
            info["bfs_progress"] = f"BFS {m.group(1)}/{m.group(2)}"

    return info


def format_ago(seconds):
    """Format a duration as a human-readable 'ago' string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        return f"{seconds/3600:.1f}h"


def format_mem(mb):
    """Format memory in human-readable form."""
    if mb >= 1024:
        return f"{mb/1024:.1f}GB"
    return f"{mb:.0f}MB"


def display_dashboard():
    """Display the monitoring dashboard."""
    now = datetime.datetime.now()
    now_ts = time.time()

    os.system("cls" if os.name == "nt" else "clear")

    print(f"{'=' * 90}")
    print(f"  S{N} Computation Monitor  |  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 90}")

    # Get completed partitions
    completed = get_completed_partitions()
    total_fpf = sum(c for c, _ in completed.values())
    n_completed = len(completed)
    total_parts = 55  # 55 FPF partitions of 16
    n_remaining = total_parts - n_completed

    print(f"\n  Partitions: {n_completed}/{total_parts} completed, "
          f"{n_remaining} remaining")
    print(f"  FPF classes: {total_fpf:,}")
    current_total = INHERITED + total_fpf
    print(f"  S16 so far: {current_total:,} (= {INHERITED:,} inherited + {total_fpf:,} FPF)")

    # Check running GAP processes
    gap_procs = check_gap_processes()
    total_mem_gb = sum(p['mem_mb'] for p in gap_procs.values()) / 1024
    print(f"\n  GAP processes: {len(gap_procs)} running "
          f"(total mem: {total_mem_gb:.1f}GB)")

    # Worker status table
    print(f"\n  {'Worker':>8} {'Round':>5} {'Status':>10} {'HB age':>7} "
          f"{'Mem':>7} {'Combo':>12} {'FPF':>7} {'Partition(s)'}")
    print(f"  {'-'*8} {'-'*5} {'-'*10} {'-'*7} "
          f"{'-'*7} {'-'*12} {'-'*7} {'-'*30}")

    for wid in sorted(WORKER_INFO.keys()):
        wi = WORKER_INFO[wid]
        hb_content, hb_mtime = read_heartbeat(wid)
        log_size, log_mtime, log_lines = get_log_info(wid)

        # Determine status
        if hb_content and "ALL DONE" in hb_content:
            status = "DONE"
        elif hb_content and "completed" in hb_content:
            status = "DONE"
        elif hb_mtime is not None:
            staleness = now_ts - hb_mtime
            if staleness > 600:
                status = "STALE"
            else:
                status = "RUNNING"
        else:
            status = "UNKNOWN"

        # Parse heartbeat
        hb_age_str = "-"
        fpf_str = "-"
        combo_str = "-"

        if hb_mtime:
            staleness = now_ts - hb_mtime
            hb_age_str = format_ago(staleness)

        if hb_content:
            m = re.search(r"combo #(\d+)", hb_content)
            if m:
                combo_num = int(m.group(1))
                for ps in wi["partitions"]:
                    try:
                        part = [int(x) for x in ps.strip("[]").split(",")]
                        total_c = total_combos_for_partition(part)
                        combo_str = f"{combo_num}/{total_c}"
                        break
                    except (ValueError, KeyError):
                        pass
                if combo_str == "-":
                    combo_str = f"#{combo_num}"

            m = re.search(r"fpf=(\d+)", hb_content)
            if m:
                fpf_str = m.group(1)

        # Memory from PID (gap.exe PIDs differ from bash wrapper PIDs)
        mem_str = "-"
        known_pid = wi.get("pid")
        if known_pid and known_pid in gap_procs:
            mem_str = format_mem(gap_procs[known_pid]["mem_mb"])

        # Partition string
        part_str = ", ".join(wi["partitions"])

        # Log-based status enrichment
        log_info = parse_log_for_status(log_lines)
        if log_info["failed_combos"] > 0 and status not in ("DONE",):
            status = f"ERR({log_info['failed_combos']})"
        if log_info["ccs_active"] and status not in ("DONE",):
            status = "CCS"
        if log_info["allsubgroups"] and status != "DONE":
            status = "AllSubs"
        if log_info["gf2_dedup"] and status != "DONE":
            status = "GF2 BFS"
        if log_info["bfs_progress"] and status != "DONE":
            status = log_info["bfs_progress"][:10]

        # Override combo/fpf from log if heartbeat is stale
        if hb_mtime and (now_ts - hb_mtime) > 120:
            if log_info["combo_num"] is not None:
                for ps in wi["partitions"]:
                    try:
                        part = [int(x) for x in ps.strip("[]").split(",")]
                        total_c = total_combos_for_partition(part)
                        combo_str = f"{log_info['combo_num']}/{total_c}"
                        break
                    except (ValueError, KeyError):
                        pass
            if log_info["fpf_total"] is not None:
                fpf_str = str(log_info["fpf_total"])

        note = wi.get("note", "")
        note_str = f"  ({note})" if note and status not in ("DONE",) else ""
        print(f"  W{wid:>6} {wi['round']:>5} {status:>10} {hb_age_str:>7} "
              f"{mem_str:>7} {combo_str:>12} {fpf_str:>7} {part_str}{note_str}")

    # Worker log tails
    print(f"\n  --- Worker Logs (last 5 meaningful lines) ---")
    skip_patterns = ["Syntax warning", "Unbound global", "loaded.", "===============",
                     "Functions:", "Config:", "Main:", "Test:", "Stats:", "Wrapper:",
                     "Caching:", "Precomputed:", "Debugging:", "Uses:", "Loaded LIFT_CACHE",
                     "Database loaded", "images package", "Database loader",
                     "Call LoadDatabase", "Loaded elementary", "Loaded transitive",
                     "Loaded ", "Loading precomputed", "Worker ", "H^1 Orbital module",
                     "Cohomology module", "Modules loaded", "Lifting Algorithm loaded",
                     "Lifting Method FAST"]
    for wid in sorted(WORKER_INFO.keys()):
        _, _, log_lines = get_log_info(wid)
        if not log_lines:
            continue
        meaningful = [l for l in log_lines
                      if l.strip()
                      and not l.strip().startswith("^")
                      and not any(p in l for p in skip_patterns)]
        if meaningful:
            print(f"\n  W{wid}:")
            for line in meaningful[-5:]:
                display = line.strip()[:100]
                if display:
                    print(f"    {display}")

    # Remaining partitions
    remaining_keys = set()
    for k in ["8_8", "8_4_4", "4_4_4_4", "4_4_4_2_2", "4_4_2_2_2_2",
              "4_2_2_2_2_2_2"]:
        if k not in completed:
            remaining_keys.add(k)

    if remaining_keys:
        print(f"\n  Remaining partitions ({len(remaining_keys)}):")
        for k in sorted(remaining_keys):
            part_str = "[" + k.replace("_", ",") + "]"
            assigned = "?"
            for wid, wi in WORKER_INFO.items():
                for ps in wi["partitions"]:
                    ps_key = ps.strip("[]").replace(",", "_").replace(" ", "")
                    if ps_key == k:
                        assigned = f"W{wid}"
                        break
            print(f"    {part_str:25s} -> {assigned}")

    # Completed partitions summary (top 10 by count)
    print(f"\n  Top 10 completed partitions:")
    for part_key, (count, wid) in sorted(completed.items(),
                                          key=lambda x: -x[1][0])[:10]:
        part_str = "[" + part_key.replace("_", ",") + "]"
        print(f"    {part_str:25s} {count:>6} (W{wid})")

    # Warnings
    warnings = []
    for wid in sorted(WORKER_INFO.keys()):
        _, _, log_lines = get_log_info(wid)
        log_info = parse_log_for_status(log_lines)
        if log_info["failed_combos"] > 0:
            warnings.append(f"W{wid}: {log_info['failed_combos']} combo(s) FAILED")

    for wid in sorted(WORKER_INFO.keys()):
        hb_content, hb_mtime = read_heartbeat(wid)
        if hb_mtime and (now_ts - hb_mtime) > 1800 and "DONE" not in (hb_content or ""):
            warnings.append(f"W{wid}: heartbeat stale for {format_ago(now_ts - hb_mtime)}")

    if warnings:
        print(f"\n  Warnings:")
        for w in warnings:
            print(f"    {w}")

    print(f"\n{'=' * 90}")


def main():
    parser = argparse.ArgumentParser(description="Monitor S16 computation progress")
    parser.add_argument("--interval", type=int, default=60,
                       help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true",
                       help="Display once and exit")
    args = parser.parse_args()

    if args.once:
        display_dashboard()
        return

    print("Starting S16 monitor (Ctrl+C to stop)...")
    try:
        while True:
            display_dashboard()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
