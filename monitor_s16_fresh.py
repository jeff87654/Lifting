###############################################################################
# monitor_s16_fresh.py - Real-time progress dashboard for fresh S16 computation
#
# Auto-discovers workers from manifest.json (no hardcoded worker table).
# Shows per-worker heartbeat, combo progress, FPF totals, memory, log tails.
#
# Usage:
#   python monitor_s16_fresh.py                  # Default 60s refresh
#   python monitor_s16_fresh.py --interval 30    # 30s refresh
#   python monitor_s16_fresh.py --once           # Single snapshot, no refresh
#
###############################################################################

import os
import sys
import time
import re
import json
import ast
import argparse
import datetime
import subprocess
from collections import Counter

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16_fresh")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")
N = 16
INHERITED = 159129   # OEIS A000638(15)
OEIS_S16 = 686165    # OEIS A000638(16)
EXPECTED_FPF = OEIS_S16 - INHERITED  # 527,036
TOTAL_PARTITIONS = 55

# Known-good spot-check values (updated from fresh run where applicable)
SPOT_CHECK = {
    "16":   1954,
    "14_2": 142,   # Fresh run found 142 (old run had 134, undercounted)
    "13_3": 26,
    "12_4": 8167,
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


# ===========================================================================
# Data collection
# ===========================================================================
def load_manifest():
    """Load manifest, return dict or None."""
    if not os.path.exists(MANIFEST_FILE):
        return None
    try:
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_worker_assignments(manifest):
    """Build worker_id -> list of partitions from manifest."""
    assignments = {}
    if manifest is None:
        return assignments
    for key, info in manifest.get("partitions", {}).items():
        wid = info.get("worker_id")
        if wid is not None:
            if wid not in assignments:
                assignments[wid] = []
            assignments[wid].append(info["partition"])
    return assignments


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


def parse_worker_results(worker_id, output_dir):
    """Parse results from a worker's result file."""
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
    partition_counts = {}
    total = 0
    worker_time = 0

    if not os.path.exists(result_file):
        return partition_counts, total, worker_time

    with open(result_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TOTAL"):
                pass
            elif line.startswith("TIME"):
                try:
                    worker_time = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
            elif line:
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    try:
                        part_str = parts[0].strip()
                        count = int(parts[1])
                        partition_counts[part_str] = count
                        total += count
                    except ValueError:
                        pass

    return partition_counts, total, worker_time


def get_completed_partitions():
    """Get all completed partitions from ALL worker result files."""
    results = {}  # part_key -> (count, worker_id)
    if not os.path.exists(OUTPUT_DIR):
        return results
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith("_results.txt") and f.startswith("worker_"):
            wid_str = f.replace("worker_", "").replace("_results.txt", "")
            try:
                wid = int(wid_str)
            except ValueError:
                continue
            try:
                with open(os.path.join(OUTPUT_DIR, f)) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("TIME") or line.startswith("TOTAL"):
                            continue
                        parts = line.rsplit(" ", 1)
                        if len(parts) == 2:
                            part_str = parts[0].strip()
                            count = int(parts[1])
                            key = part_str.replace("[", "").replace("]", "").replace(" ", "").replace(",", "_")
                            if key not in results or count > results[key][0]:
                                results[key] = (count, wid)
            except (IOError, ValueError):
                pass
    return results


def check_gap_processes():
    """Check which GAP PIDs are running and their resource usage.
    Returns dict of pid -> {cpu_s, mem_mb, parent_pid, cmdline}.
    """
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='gap.exe'", "get",
             "ProcessId,ParentProcessId,UserModeTime,WorkingSetSize", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        processes = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 5 and parts[1].isdigit():
                parent_pid = int(parts[1])
                pid = int(parts[2])
                user_time = int(parts[3]) / 10_000_000  # 100ns -> seconds
                mem_bytes = int(parts[4])
                processes[pid] = {
                    "cpu_s": user_time,
                    "mem_mb": mem_bytes / (1024 * 1024),
                    "parent_pid": parent_pid,
                }
        return processes
    except Exception:
        return {}


def get_checkpoint_recovery_info():
    """Scan checkpoint dirs for recovered .log files.
    Returns dict: worker_id -> {partition_key: (loaded_combos, loaded_fpf)}.
    """
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    if not os.path.exists(ckpt_base):
        return {}
    recovery = {}
    for entry in os.listdir(ckpt_base):
        if not entry.startswith("worker_"):
            continue
        try:
            wid = int(entry.replace("worker_", ""))
        except ValueError:
            continue
        wdir = os.path.join(ckpt_base, entry)
        for fn in os.listdir(wdir):
            if not fn.startswith("ckpt_16_") or not fn.endswith(".log"):
                continue
            fpath = os.path.join(wdir, fn)
            try:
                combos = 0
                fpf = 0
                with open(fpath, "r", errors="replace") as f:
                    for line in f:
                        if line.startswith("# end combo"):
                            combos += 1
                            m = re.search(r'\((\d+) total fpf\)', line)
                            if m:
                                fpf = int(m.group(1))
                if combos > 0:
                    part_key = fn.replace("ckpt_16_", "").replace(".log", "")
                    if wid not in recovery:
                        recovery[wid] = {}
                    recovery[wid][part_key] = (combos, fpf)
            except (OSError, IOError):
                pass
    return recovery


def map_pids_to_workers(gap_procs, manifest):
    """Map GAP PIDs to worker IDs via parent bash PIDs.

    Strategy 1: Read master log for "Worker N launched (PID xxx)" lines.
    Strategy 2: Scan running bash.exe processes for worker_N.g in command line.
    """
    pid_to_worker = {}
    bash_pid_to_worker = {}

    # Strategy 1: master log
    log_file = os.path.join(OUTPUT_DIR, "run_s16_fresh.log")
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                for line in f:
                    m = re.search(r"Worker (\d+) launched \(PID (\d+)\)", line)
                    if m:
                        wid = int(m.group(1))
                        bash_pid = int(m.group(2))
                        bash_pid_to_worker[bash_pid] = wid
        except IOError:
            pass

    # Strategy 2: scan bash.exe processes for worker_N.g in command line
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
                m = re.search(r"worker_(\d+)\.g", cmdline)
                if m:
                    try:
                        wid = int(m.group(1))
                        bash_pid = int(parts[1])
                        bash_pid_to_worker[bash_pid] = wid
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass

    for gap_pid, info in gap_procs.items():
        parent = info.get("parent_pid")
        if parent in bash_pid_to_worker:
            pid_to_worker[gap_pid] = bash_pid_to_worker[parent]

    return pid_to_worker


def parse_log_for_status(lines):
    """Extract status information from log lines."""
    info = {
        "current_partition": None,
        "current_combo": None,
        "combo_num": None,
        "fpf_total": None,
        "elapsed": None,
        "gf2_dedup": False,
        "ccs_active": False,
        "goursat_active": False,
        "failed_combos": 0,
        "last_layer": None,
        "bfs_progress": None,
        "completed_parts": [],
    }

    for line in lines:
        # Combo completion
        m = re.search(r"combo #(\d+) done \((\d+\.?\d*)s elapsed, (\d+) fpf total\)", line)
        if m:
            info["combo_num"] = int(m.group(1))
            info["elapsed"] = float(m.group(2))
            info["fpf_total"] = int(m.group(3))

        # Current combo
        m = re.search(r">> combo \[\[ (.+?) \]\]", line)
        if m:
            info["current_combo"] = f"[[{m.group(1).replace(' ', '')}]]"

        # Current partition
        m = re.search(r"Partition \[(.+?)\]", line)
        if m:
            info["current_partition"] = f"[{m.group(1).replace(' ', '')}]"

        # Partition completion
        m = re.search(r"=> (\d+) classes \((\d+\.?\d*)s\)", line)
        if m:
            info["completed_parts"].append((int(m.group(1)), float(m.group(2))))

        if "GF(2) orbit dedup" in line or "GF(" in line:
            info["gf2_dedup"] = True

        if "CCS fast path" in line or "CCS dedup" in line:
            info["ccs_active"] = True

        if "Goursat" in line:
            info["goursat_active"] = True

        if "combo FAILED" in line:
            info["failed_combos"] += 1

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


def format_time(seconds):
    """Format seconds as Xh Ym or Ym Zs."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h{m:02d}m"
    elif seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m{s:02d}s"
    else:
        return f"{seconds:.0f}s"


# ===========================================================================
# Dashboard display
# ===========================================================================
def display_dashboard():
    """Display the monitoring dashboard."""
    now = datetime.datetime.now()
    now_ts = time.time()

    os.system("cls" if os.name == "nt" else "clear")

    print(f"{'=' * 95}")
    print(f"  S{N} Fresh Computation Monitor  |  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 95}")

    # Load manifest for worker assignments
    manifest = load_manifest()
    worker_assignments = get_worker_assignments(manifest)
    worker_ids = sorted(worker_assignments.keys())

    # Compute start time from manifest
    start_str = manifest.get("created", "") if manifest else ""
    wall_time_str = ""
    if start_str:
        try:
            start_dt = datetime.datetime.fromisoformat(start_str)
            wall_seconds = (now - start_dt).total_seconds()
            wall_time_str = f"  |  Wall: {format_time(wall_seconds)}"
        except (ValueError, TypeError):
            pass

    # Get completed partitions
    completed = get_completed_partitions()
    total_fpf = sum(c for c, _ in completed.values())
    n_completed = len(completed)
    n_remaining = TOTAL_PARTITIONS - n_completed

    pct_parts = n_completed / TOTAL_PARTITIONS * 100
    pct_fpf = total_fpf / EXPECTED_FPF * 100 if EXPECTED_FPF > 0 else 0

    print(f"\n  Partitions: {n_completed}/{TOTAL_PARTITIONS} completed ({pct_parts:.0f}%), "
          f"{n_remaining} remaining{wall_time_str}")
    print(f"  FPF classes: {total_fpf:,} / {EXPECTED_FPF:,} ({pct_fpf:.1f}%)")
    current_total = INHERITED + total_fpf
    print(f"  S16 so far:  {current_total:,} / {OEIS_S16:,} "
          f"(= {INHERITED:,} inherited + {total_fpf:,} FPF)")

    # Progress bar
    bar_width = 50
    filled = int(bar_width * n_completed / TOTAL_PARTITIONS)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"  [{bar}] {pct_parts:.0f}%")

    # Check running GAP processes and map to workers
    gap_procs = check_gap_processes()
    pid_to_worker = map_pids_to_workers(gap_procs, manifest)
    worker_to_pid = {wid: pid for pid, wid in pid_to_worker.items()}

    # Separate project workers from other GAP processes
    project_pids = set(pid_to_worker.keys())
    other_procs = {p: info for p, info in gap_procs.items() if p not in project_pids}
    project_mem_gb = sum(gap_procs[p]['mem_mb'] for p in project_pids) / 1024
    other_mem_gb = sum(info['mem_mb'] for info in other_procs.values()) / 1024
    total_mem_gb = sum(p['mem_mb'] for p in gap_procs.values()) / 1024

    print(f"\n  GAP processes: {len(project_pids)} workers + {len(other_procs)} other "
          f"(workers: {project_mem_gb:.1f}GB, other: {other_mem_gb:.1f}GB, "
          f"total: {total_mem_gb:.1f}GB)")

    # Get checkpoint recovery info
    ckpt_info = get_checkpoint_recovery_info()

    # Classify workers as active vs finished
    active_wids = []
    finished_wids = []
    dead_wids = []

    for wid in worker_ids:
        parts = worker_assignments[wid]
        worker_result_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_results.txt")
        worker_done = 0
        has_total = False
        if os.path.exists(worker_result_file):
            try:
                with open(worker_result_file) as rf:
                    for line in rf:
                        line = line.strip()
                        if line.startswith("TOTAL"):
                            has_total = True
                        elif line and not line.startswith("TIME"):
                            worker_done += 1
            except IOError:
                pass

        if has_total:
            # Worker wrote TOTAL line — it ran to completion
            finished_wids.append((wid, worker_done, parts))
        elif worker_done == len(parts) and worker_done > 0:
            # All assigned partitions have results (may have been reassigned)
            finished_wids.append((wid, worker_done, parts))
        elif wid in worker_to_pid:
            active_wids.append(wid)
        else:
            # No mapped PID — check heartbeat and log freshness
            hb_content, hb_mtime = read_heartbeat(wid)
            log_size, log_mtime_val, _ = get_log_info(wid)
            # Consider active if heartbeat or log updated within 30 min
            recently_active = False
            if hb_mtime and (now_ts - hb_mtime) < 1800:
                recently_active = True
            if log_mtime_val and (now_ts - log_mtime_val) < 1800:
                recently_active = True
            if recently_active:
                active_wids.append(wid)  # Recently active (unmapped PID)
            elif worker_done > 0:
                dead_wids.append((wid, worker_done, len(parts)))
            else:
                dead_wids.append((wid, worker_done, len(parts)))

    # Finished workers summary
    if finished_wids:
        total_finished_fpf = 0
        for wid, wdone, parts in finished_wids:
            pc, total, wtime = parse_worker_results(wid, OUTPUT_DIR)
            total_finished_fpf += total
        print(f"\n  Finished workers: {len(finished_wids)} "
              f"({total_finished_fpf:,} FPF from "
              f"{sum(wd for _, wd, _ in finished_wids)} partitions)")
        for wid, wdone, parts in finished_wids:
            pc, total, wtime = parse_worker_results(wid, OUTPUT_DIR)
            time_str = format_time(wtime) if wtime > 0 else "-"
            print(f"    W{wid}: {wdone} partitions, {total:,} FPF, {time_str}")

    # Dead workers
    if dead_wids:
        print(f"\n  Dead/killed workers: {len(dead_wids)} (incomplete partitions reassigned)")
        for wid, wdone, n_parts in dead_wids:
            print(f"    W{wid}: {wdone}/{n_parts} done before killed")

    # Active workers - detailed table
    if active_wids:
        print(f"\n  {'Worker':>6} {'Status':>10} {'HB age':>7} {'Mem':>8} "
              f"{'Combo':>12} {'FPF':>7} {'ETA':>7} {'Current partition'}")
        print(f"  {'-'*6} {'-'*10} {'-'*7} {'-'*8} "
              f"{'-'*12} {'-'*7} {'-'*7} {'-'*40}")

    for wid in active_wids:
        parts = worker_assignments[wid]
        hb_content, hb_mtime = read_heartbeat(wid)
        log_size, log_mtime, log_lines = get_log_info(wid)
        log_info = parse_log_for_status(log_lines)

        # Count completed partitions for this worker
        worker_result_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_results.txt")
        worker_done = 0
        if os.path.exists(worker_result_file):
            try:
                with open(worker_result_file) as rf:
                    for line in rf:
                        line = line.strip()
                        if line and not line.startswith("TOTAL") and not line.startswith("TIME"):
                            worker_done += 1
            except IOError:
                pass

        # Determine status
        if hb_mtime is not None:
            staleness = now_ts - hb_mtime
            if staleness > 600:
                status = "STALE"
            else:
                status = "RUNNING"
        elif log_mtime is not None:
            status = "STARTING"
        else:
            status = "UNKNOWN"

        # Enrich status from log
        if status not in ("UNKNOWN", "STARTING"):
            if log_info["failed_combos"] > 0:
                status = f"ERR({log_info['failed_combos']})"
            elif log_info["goursat_active"]:
                status = "GOURSAT"
            elif log_info["ccs_active"]:
                status = "CCS"
            elif log_info["gf2_dedup"]:
                status = "GF2"
            elif log_info["bfs_progress"]:
                status = log_info["bfs_progress"][:10]

        # Heartbeat age
        hb_age_str = "-"
        if hb_mtime:
            hb_age_str = format_ago(now_ts - hb_mtime)

        # Parse heartbeat for combo/FPF info
        fpf_str = "-"
        combo_str = "-"
        current_part_str = ""

        if hb_content:
            m = re.search(r"combo #(\d+)", hb_content)
            if m:
                combo_num = int(m.group(1))
                m_part = re.search(r"\[[\d,\s]+\]", hb_content)
                if m_part:
                    try:
                        current_part = [int(x) for x in
                                       m_part.group().strip("[]").replace(" ", "").split(",")]
                        total_c = total_combos_for_partition(current_part)
                        combo_str = f"{combo_num}/{total_c}"
                        current_part_str = str(current_part)
                    except (ValueError, KeyError):
                        combo_str = f"#{combo_num}"
                else:
                    combo_str = f"#{combo_num}"

            m = re.search(r"fpf=(\d+)", hb_content)
            if m:
                fpf_str = m.group(1)

            if "starting partition" in hb_content:
                m_part = re.search(r"\[[\d,\s]+\]", hb_content)
                if m_part:
                    current_part_str = m_part.group().replace(" ", "")
                    combo_str = "starting"

            if "completed partition" in hb_content:
                m_part = re.search(r"\[[\d,\s]+\]", hb_content)
                if m_part:
                    current_part_str = m_part.group().replace(" ", "")
                m_cnt = re.search(r"= (\d+) classes", hb_content)
                if m_cnt:
                    fpf_str = m_cnt.group(1)

        # Override from log if heartbeat is stale
        if hb_mtime and (now_ts - hb_mtime) > 120:
            if log_info["combo_num"] is not None:
                if log_info["current_partition"]:
                    try:
                        cp = [int(x) for x in
                              log_info["current_partition"].strip("[]").split(",")]
                        total_c = total_combos_for_partition(cp)
                        combo_str = f"{log_info['combo_num']}/{total_c}"
                        current_part_str = log_info["current_partition"]
                    except (ValueError, KeyError):
                        combo_str = f"#{log_info['combo_num']}"
            if log_info["fpf_total"] is not None:
                fpf_str = str(log_info["fpf_total"])

        # Memory: try PID mapping, fall back to average
        mem_str = "-"
        gap_pid = worker_to_pid.get(wid)
        if gap_pid and gap_pid in gap_procs:
            mem_str = format_mem(gap_procs[gap_pid]["mem_mb"])
        elif gap_procs and active_wids:
            # Unmapped — show average of active processes
            active_pids = [p for p in gap_procs if gap_procs[p]["mem_mb"] > 1]
            if active_pids:
                avg = sum(gap_procs[p]["mem_mb"] for p in active_pids) / len(active_pids)
                mem_str = f"~{format_mem(avg)}"

        # Summary of this worker's partitions
        if not current_part_str:
            if len(parts) == 1:
                current_part_str = str(parts[0])
            else:
                current_part_str = f"{worker_done}/{len(parts)} parts done"

        # ETA: estimate based on combo progress
        eta_str = "-"
        if combo_str and "/" in combo_str:
            try:
                c_done, c_total = combo_str.split("/")
                c_done = int(c_done)
                c_total = int(c_total)
                if c_done > 0 and c_total > 0:
                    # Get elapsed time from heartbeat
                    m_elapsed = re.search(r"alive (\d+)s", hb_content or "")
                    if m_elapsed:
                        elapsed_s = int(m_elapsed.group(1))
                        rate = elapsed_s / c_done if c_done > 0 else 0
                        remaining = rate * (c_total - c_done)
                        eta_str = format_time(remaining)
            except (ValueError, TypeError):
                pass

        # Show checkpoint recovery note
        ckpt_note = ""
        if wid in ckpt_info:
            for pk, (ck_combos, ck_fpf) in ckpt_info[wid].items():
                part_key = current_part_str.replace("[", "").replace("]", "").replace(",", "_").replace(" ", "")
                if pk == part_key:
                    ckpt_note = f" (ckpt:{ck_combos})"
                    break

        print(f"  W{wid:>4} {status:>10} {hb_age_str:>7} {mem_str:>8} "
              f"{combo_str:>12} {fpf_str:>7} {eta_str:>7} {current_part_str}{ckpt_note}")

    # Spot checks
    spot_results = []
    all_ok = True
    for key, expected in sorted(SPOT_CHECK.items()):
        if key in completed:
            actual = completed[key][0]
            ok = actual == expected
            if not ok:
                all_ok = False
            spot_results.append((key, actual, expected, ok))
        else:
            spot_results.append((key, None, expected, None))

    if spot_results:
        print(f"\n  Spot checks:")
        for key, actual, expected, ok in spot_results:
            part_str = "[" + key.replace("_", ",") + "]"
            if actual is not None:
                status = "OK" if ok else f"FAIL (expected {expected})"
                print(f"    {part_str:15s} {actual:>6}  {status}")
            else:
                print(f"    {part_str:15s}      -  (pending)")

    # Top completed partitions
    if completed:
        print(f"\n  Top 10 partitions by FPF count:")
        sorted_completed = sorted(completed.items(), key=lambda x: -x[1][0])
        for key, (count, wid) in sorted_completed[:10]:
            part_str = "[" + key.replace("_", ",") + "]"
            print(f"    {part_str:25s} {count:>7,} (W{wid})")

    # Remaining (not yet completed) partitions
    if n_remaining > 0 and n_remaining <= 35:
        print(f"\n  Remaining partitions ({n_remaining}):")
        for key, info in sorted(manifest["partitions"].items()):
            if key not in completed:
                part_str = "[" + key.replace("_", ",") + "]"
                wid = info.get("worker_id", "?")
                # Check for checkpoint recovery
                ckpt_str = ""
                if wid in ckpt_info and key in ckpt_info[wid]:
                    ck_combos, ck_fpf = ckpt_info[wid][key]
                    try:
                        part_list = [int(x) for x in key.split("_")]
                        tc = total_combos_for_partition(part_list)
                        ckpt_str = f" [ckpt: {ck_combos}/{tc}, {ck_fpf} fpf]"
                    except (ValueError, KeyError):
                        ckpt_str = f" [ckpt: {ck_combos} combos]"
                print(f"    {part_str:25s} -> W{wid}{ckpt_str}")

    # Worker log tails (active workers only)
    skip_patterns = [
        "Syntax warning", "Unbound global", "loaded.", "===============",
        "Functions:", "Config:", "Main:", "Test:", "Stats:", "Wrapper:",
        "Caching:", "Precomputed:", "Debugging:", "Uses:", "Loaded LIFT_CACHE",
        "Database loaded", "images package", "Database loader",
        "Call LoadDatabase", "Loaded elementary", "Loaded transitive",
        "Loaded ", "Loading precomputed", "Worker ", "H^1 Orbital module",
        "Cohomology module", "Modules loaded", "Lifting Algorithm loaded",
        "Lifting Method FAST", "Processing ",
    ]
    if active_wids:
        print(f"\n  --- Active Worker Log Tails ---")
        for wid in active_wids:
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

    # Warnings (active workers only)
    warnings = []
    for wid in active_wids:
        _, _, log_lines = get_log_info(wid)
        log_info = parse_log_for_status(log_lines)
        if log_info["failed_combos"] > 0:
            warnings.append(f"W{wid}: {log_info['failed_combos']} combo(s) FAILED")

    for wid in active_wids:
        hb_content, hb_mtime = read_heartbeat(wid)
        if hb_mtime and (now_ts - hb_mtime) > 1800:
            if not (hb_content and "DONE" in hb_content.upper()):
                warnings.append(f"W{wid}: heartbeat stale for "
                              f"{format_ago(now_ts - hb_mtime)}")

    # Check for thrashing (active GAP process with <10MB memory)
    for gap_pid, info in gap_procs.items():
        if info["mem_mb"] < 10:
            wid_str = f"W{pid_to_worker[gap_pid]}" if gap_pid in pid_to_worker else f"PID {gap_pid}"
            warnings.append(f"{wid_str}: GAP process has only "
                          f"{format_mem(info['mem_mb'])} memory — likely thrashing!")

    if warnings:
        print(f"\n  WARNINGS:")
        for w in warnings:
            print(f"    ! {w}")

    print(f"\n{'=' * 95}")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor fresh S16 computation progress")
    parser.add_argument("--interval", type=int, default=60,
                       help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true",
                       help="Display once and exit")
    args = parser.parse_args()

    if args.once:
        display_dashboard()
        return

    print("Starting S16 fresh monitor (Ctrl+C to stop)...")
    try:
        while True:
            display_dashboard()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
