"""Launch GAP workers as independent background processes.

Each worker runs as a fully independent process - no monitoring Python runner
that can die and kill all workers. Workers write results to their own files
and checkpoint regularly.

Usage:
  python launch_workers.py                    # Launch all remaining (max 8 concurrent)
  python launch_workers.py --max-workers 4    # Limit concurrent workers
  python launch_workers.py --check            # Just check status
"""
import subprocess
import os
import sys
import json
import glob
import time

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(BASE_DIR, "parallel_s17")
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

INHERITED_FROM_S16 = 686165
OEIS_S17 = 1466358
EXPECTED_FPF = OEIS_S17 - INHERITED_FROM_S16  # = 780,193

NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954, 17: 5,
}


def get_completed_partitions():
    """Parse all results files to find completed partitions."""
    completed = {}
    for fn in glob.glob(os.path.join(OUTPUT_DIR, "worker_*_results.txt")):
        with open(fn) as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    parts_str, count_str = line.rsplit("]", 1)
                    parts = tuple(int(x) for x in parts_str.strip("[ ").replace(" ", "").split(","))
                    count = int(count_str.strip())
                    completed[parts] = count
    return completed


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


def find_best_checkpoint(partition):
    """Find the best checkpoint .log for a partition across all worker dirs."""
    part_str = "_".join(str(x) for x in partition)
    log_name = f"ckpt_17_{part_str}.log"
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")

    best_log = None
    best_combos = 0

    if not os.path.exists(ckpt_base):
        return None, 0

    for entry in os.listdir(ckpt_base):
        candidate = os.path.join(ckpt_base, entry, log_name)
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", errors="replace") as f:
                combo_count = sum(1 for line in f if line.startswith("# end combo"))
            if combo_count > best_combos:
                best_combos = combo_count
                best_log = candidate
        except (OSError, IOError):
            continue

    return best_log, best_combos


def create_worker_script(partition, worker_id):
    """Create a GAP script for a single partition."""
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    os.makedirs(ckpt_dir, exist_ok=True)

    hb_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")
    results_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt").replace("\\", "/")
    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log").replace("\\", "/")

    part_str = str(list(partition)).replace(" ", "")

    script = f'''LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{hb_file}";
CHECKPOINT_DIR := "{ckpt_dir}";

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

PrintTo("{hb_file}", "starting partition {part_str}\\n");

partStart := Runtime();
fpf_classes := FindFPFClassesForPartition(17, {part_str});
partTime := (Runtime() - partStart) / 1000.0;
Print("  Time: ", partTime, "s\\n");
Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");

PrintTo("{hb_file}",
    "completed partition {part_str} = ", Length(fpf_classes), " classes\\n");

AppendTo("{results_file}", "{part_str} ", Length(fpf_classes), "\\n");

LogTo();
QUIT;
'''

    script_path = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.g")
    with open(script_path, "w") as f:
        f.write(script)

    return script_path


def copy_best_checkpoint(partition, worker_id):
    """Copy the best checkpoint file to the new worker's checkpoint dir."""
    best_log, best_combos = find_best_checkpoint(partition)
    if best_log and best_combos > 0:
        part_str = "_".join(str(x) for x in partition)
        log_name = f"ckpt_17_{part_str}.log"
        dest_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}")
        dest = os.path.join(dest_dir, log_name)
        if not os.path.exists(dest) or os.path.getsize(dest) == 0:
            import shutil
            shutil.copy2(best_log, dest)
            return best_combos
    return 0


def launch_worker(script_path, worker_id):
    """Launch a single GAP worker as a fully independent process.

    Uses bash + shell script via .bat + os.startfile() with auto-restart on crash.
    Create a STOP file in OUTPUT_DIR to halt all workers.
    """
    script_cygwin = script_path.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    # Create a shell script that runs GAP
    sh_path = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.sh")
    sh_cygwin = sh_path.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
    with open(sh_path, "w", newline='\n') as f:
        f.write('#!/bin/bash\n')
        f.write('cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"\n')
        f.write(f'./gap.exe -q "{script_cygwin}"\n')

    # Create a .bat file with auto-restart and stop-file support
    results_path = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
    stop_file = os.path.join(OUTPUT_DIR, "STOP")
    bat_path = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.bat")
    with open(bat_path, "w") as f:
        f.write('@echo off\n')
        f.write('set PATH=C:\\Program Files\\GAP-4.15.1\\runtime\\bin;%PATH%\n')
        f.write('set CYGWIN=nodosfilewarning\n')
        f.write(f'echo Starting worker {worker_id}\n')
        f.write(':retry\n')
        # Check for stop file
        f.write(f'if exist "{stop_file}" goto done\n')
        f.write(f'"C:\\Program Files\\GAP-4.15.1\\runtime\\bin\\bash.exe" --login "{sh_cygwin}"\n')
        # Check if result was written (partition completed)
        f.write(f'if exist "{results_path}" (\n')
        f.write(f'  for %%A in ("{results_path}") do if %%~zA GTR 0 goto done\n')
        f.write(')\n')
        # Check for stop file again before restart
        f.write(f'if exist "{stop_file}" goto done\n')
        f.write('echo GAP exited without result, restarting in 10 seconds...\n')
        f.write('timeout /t 10 /nobreak >nul\n')
        f.write('goto retry\n')
        f.write(':done\n')
        f.write(f'echo Worker {worker_id} finished.\n')

    # Use a VBS wrapper to launch the bat file silently (no visible window)
    vbs_path = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.vbs")
    with open(vbs_path, "w") as f:
        f.write(f'Set WshShell = CreateObject("WScript.Shell")\n')
        f.write(f'WshShell.Run """{bat_path}""", 0, False\n')
    os.startfile(vbs_path)
    return 0  # PID not available via os.startfile


def get_worker_partition(worker_id):
    """Read the .g script to find which partition a worker is computing."""
    script = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.g")
    if not os.path.exists(script):
        return None
    with open(script) as f:
        for line in f:
            if "FindFPFClassesForPartition" in line:
                # Extract partition from e.g. FindFPFClassesForPartition(17, [8,6,3]);
                import re
                m = re.search(r'\[[\d,]+\]', line)
                if m:
                    return tuple(int(x) for x in m.group().strip("[]").split(","))
    return None


def check_status():
    """Check the status of all partitions."""
    completed = get_completed_partitions()
    all_parts = partitions_no_ones(17)
    missing = [p for p in all_parts if p not in completed]

    total_fpf = sum(completed.values())
    total_s17 = INHERITED_FROM_S16 + total_fpf
    pct = total_fpf * 100 / EXPECTED_FPF
    print(f"S17 progress: {len(completed)}/66 partitions, "
          f"{total_fpf:,}/{EXPECTED_FPF:,} FPF ({pct:.1f}%), "
          f"{total_s17:,}/{OEIS_S17:,} total")
    print()

    # Find active workers: check which log files are recently modified
    # Group by partition so we show one line per partition, not per worker
    active_by_partition = {}  # partition -> (wid, heartbeat_info, log_age)
    for fn in glob.glob(os.path.join(OUTPUT_DIR, "worker_*.log")):
        wid_str = os.path.basename(fn).replace("worker_", "").replace(".log", "")
        try:
            wid = int(wid_str)
        except ValueError:
            continue
        log_age = time.time() - os.path.getmtime(fn)
        if log_age > 600:  # Not updated in 10 min = dead
            continue
        partition = get_worker_partition(wid)
        if partition is None or partition in completed:
            continue
        # Read heartbeat for detail
        hb_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
        hb_info = ""
        if os.path.exists(hb_file):
            with open(hb_file) as f:
                hb_info = f.read().strip()
        # Keep the most recent worker per partition
        if partition not in active_by_partition or wid > active_by_partition[partition][0]:
            active_by_partition[partition] = (wid, hb_info, log_age)

    if active_by_partition:
        print(f"Active workers ({len(active_by_partition)}):")
        for p in sorted(active_by_partition.keys()):
            wid, hb_info, log_age = active_by_partition[p]
            _, ckpt = find_best_checkpoint(p)
            combos = 1
            for d in p:
                combos *= NR_TRANSITIVE[d]
            # Extract combo/fpf from heartbeat if available
            detail = ""
            if "combo #" in hb_info:
                detail = hb_info.split("combo #")[1].split("\n")[0]
                detail = f"  combo {detail}"
            elif "completed" in hb_info:
                detail = "  finishing..."
            print(f"  {str(list(p)):25s} {ckpt:>4}/{combos:<4} ({ckpt*100/combos:4.0f}%){detail}")
        print()

    # Show missing partitions without active workers
    idle_missing = [p for p in missing if p not in active_by_partition]
    if idle_missing:
        print(f"Waiting ({len(idle_missing)} partitions, no active worker):")
        for p in idle_missing:
            _, ckpt = find_best_checkpoint(p)
            combos = 1
            for d in p:
                combos *= NR_TRANSITIVE[d]
            print(f"  {str(list(p)):25s} {ckpt:>4}/{combos:<4} ({ckpt*100/combos:4.0f}%)")


def main():
    if "--check" in sys.argv:
        check_status()
        return

    # Parse --max-workers
    max_workers = 8
    for i, arg in enumerate(sys.argv):
        if arg == "--max-workers" and i + 1 < len(sys.argv):
            max_workers = int(sys.argv[i + 1])

    completed = get_completed_partitions()
    all_parts = partitions_no_ones(17)
    missing = [p for p in all_parts if p not in completed]

    if not missing:
        print("All 66 partitions completed!")
        check_status()
        return

    # Sort by remaining combos (fewest first = closest to completion)
    def remaining_combos(partition):
        total = 1
        for d in partition:
            total *= NR_TRANSITIVE[d]
        _, ckpt = find_best_checkpoint(partition)
        return total - ckpt

    missing.sort(key=remaining_combos)

    # Only launch up to max_workers
    to_launch = missing[:max_workers]
    print(f"{len(missing)} partitions remaining, launching {len(to_launch)} workers (max {max_workers})...")

    # Find next worker ID
    existing = glob.glob(os.path.join(OUTPUT_DIR, "worker_*.g"))
    max_id = max((int(os.path.basename(f).replace("worker_", "").replace(".g", ""))
                   for f in existing), default=-1)
    next_id = max_id + 1

    launched = []
    for i, partition in enumerate(to_launch):
        wid = next_id + i
        script = create_worker_script(partition, wid)
        ckpt_recovered = copy_best_checkpoint(partition, wid)
        pid = launch_worker(script, wid)
        combos = 1
        for d in partition:
            combos *= NR_TRANSITIVE[d]
        ckpt_info = f" (ckpt: {ckpt_recovered} combos)" if ckpt_recovered > 0 else ""
        print(f"  W{wid} (PID {pid}): {list(partition)} [{combos} combos]{ckpt_info}")
        launched.append((wid, partition, pid))

    print(f"\nLaunched {len(launched)} independent workers (of {len(missing)} remaining)")
    print("Workers run independently - this script can exit safely.")
    print("Check progress: python launch_workers.py --check")
    print("Launch more:    python launch_workers.py")


if __name__ == "__main__":
    main()
