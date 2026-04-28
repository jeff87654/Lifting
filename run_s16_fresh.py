###############################################################################
# run_s16_fresh.py - Fresh S16 computation from scratch
#
# Clean recomputation of all 55 FPF partitions of 16 using the current
# verified code (Phase C1 + series stabilizer + Goursat + all optimizations).
#
# Derived from run_s16.py with:
#   - New output directory: parallel_s16_fresh/
#   - Updated cost estimates from actual S16 timing data
#   - 24h timeout per worker
#   - OEIS A000638(16) = 686,165 target (FPF = 527,036)
#
# Usage:
#   python run_s16_fresh.py --dry-run               # Preview assignment
#   python run_s16_fresh.py                          # Launch computation
#   python run_s16_fresh.py --workers 4              # Use 4 workers instead of 8
#   python run_s16_fresh.py --resume                 # Resume incomplete partitions
#   python run_s16_fresh.py --combine-only           # Assemble final cache
#
###############################################################################

import subprocess
import os
import sys
import time
import re
import ast
import json
import argparse
import datetime
import shutil
from pathlib import Path
from collections import Counter

# ===========================================================================
# Configuration
# ===========================================================================
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
CONJUGACY_CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
N = 16
INHERITED_FROM_S15 = 159129  # OEIS A000638(15)
OEIS_S16 = 686165            # OEIS A000638(16)
EXPECTED_FPF = OEIS_S16 - INHERITED_FROM_S15  # = 527,036

# NrTransitiveGroups for degrees 1..16
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954,
}

# Actual S16 cost data (seconds) from previous runs.
# Used for accurate LPT scheduling instead of heuristic extrapolation.
S16_ACTUAL_COST = {
    # Tier 1: 3-8h each (one per worker)
    (8, 4, 4):       40000,
    (8, 4, 2, 2):    27000,
    (4, 4, 4, 4):    25000,
    (4, 4, 4, 2, 2): 22000,
    # Tier 2: 1-3h each
    (8, 6, 2):       45000,  # W4 spent 38380s at 57% done → ~67000s; adjusted for fewer workers
    (6, 4, 4, 2):    15000,  # W5 at combo 234/240 after 14024s
    (6, 4, 2, 2, 2): 10000,
    (6, 6, 4):        8000,
    (8, 8):            5000,  # Much faster with Goursat
    (4, 4, 2, 2, 2, 2): 8000,
    (12, 4):           4500,
    (4, 4, 3, 3, 2):   4000,
    # Tier 3: 15min-1h
    (6, 4, 3, 3):     3500,
    (9, 4, 3):        3500,  # 340 combos, max_part=9
    (6, 6, 2, 2):     3000,
    (8, 2, 2, 2, 2):  3000,
    (8, 3, 3, 2):     2500,
    (5, 4, 4, 3):     2000,
    (8, 5, 3):        2000,
    (7, 6, 3):        2000,  # 224 combos
    (7, 5, 4):        2000,  # 175 combos
    (10, 4, 2):       1800,
    (6, 3, 3, 2, 2):  1500,
    (10, 6):          1500,
    (7, 7, 2):        1500,  # 24 combos, Goursat-ish
    (5, 5, 4, 2):     1500,
    (8, 3, 2, 2, 2):  1200,
    (5, 4, 3, 2, 2):  1200,
    (10, 2, 2, 2):    1000,
    (6, 3, 2, 2, 2, 2): 1000,
    (5, 3, 3, 3, 2):  800,
    (5, 5, 3, 3):     800,
    (10, 3, 3):       700,
    (7, 5, 2, 2):     600,
    (8, 5, 2, 2):     600,
    (9, 7):           500,   # 238 combos, Goursat
    (7, 3, 3, 3):     500,   # 9 combos after symmetry
    # Tier 4: <15 min
    (12, 2, 2):       400,
    (14, 2):          300,
    (12, 3, 2):       300,
    (11, 3, 2):       300,
    (5, 5, 2, 2, 2):  400,
    (4, 3, 3, 2, 2, 2): 400,
    (4, 3, 3, 3, 3):  300,
    (3, 3, 3, 3, 2, 2): 200,
    (5, 3, 2, 2, 2, 2): 200,
    (7, 3, 2, 2, 2):  200,
    (13, 3):          100,   # 18 combos, Goursat
    (3, 3, 3, 2, 2, 2, 2): 100,
    (6, 2, 2, 2, 2, 2): 100,
    (3, 3, 2, 2, 2, 2, 2): 50,
    (4, 2, 2, 2, 2, 2, 2): 50,
    (3, 2, 2, 2, 2, 2, 2, 2): 20,
    (2, 2, 2, 2, 2, 2, 2, 2): 10,
    (16,):            5,
}

# Default timeout per worker: 24 hours
DEFAULT_TIMEOUT = 86400
# Heartbeat staleness threshold (seconds)
HEARTBEAT_STALE_THRESHOLD = 600  # 10 minutes

OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16_fresh")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")
MASTER_LOG = os.path.join(OUTPUT_DIR, "run_s16_fresh.log")


# ===========================================================================
# Utility: partition generation
# ===========================================================================
def partitions_min_part(n, min_part=2):
    """Generate all partitions of n with all parts >= min_part, sorted descending."""
    result = []

    def helper(remaining, max_part, current):
        if remaining == 0:
            result.append(tuple(current))
            return
        for i in range(min(remaining, max_part), min_part - 1, -1):
            current.append(i)
            helper(remaining - i, i, current)
            current.pop()

    helper(n, n, [])
    return result


def partition_key(partition):
    """Convert partition tuple/list to a string key like '8_4_4'."""
    return "_".join(str(x) for x in partition)


def partition_from_key(key):
    """Convert string key '8_4_4' back to a tuple."""
    return tuple(int(x) for x in key.split("_"))


def partition_gap_str(partition):
    """Format partition as GAP list string like '[8,4,4]'."""
    return "[" + ",".join(str(x) for x in partition) + "]"


# ===========================================================================
# Cost estimation
# ===========================================================================
def estimate_partition_cost(partition):
    """Estimate cost of a partition based on actual S16 data and heuristics.

    Uses actual S16 timing data when available, otherwise falls back to
    combo-count heuristic.
    """
    pt = tuple(partition)

    # Direct lookup in actual S16 data (most accurate)
    if pt in S16_ACTUAL_COST:
        return S16_ACTUAL_COST[pt]

    # Single-part partitions are near-instant
    if len(partition) == 1:
        nr = NR_TRANSITIVE.get(partition[0], 100)
        return max(0.1, nr * 0.005)

    # Fallback: combo-count heuristic
    n = sum(partition)
    k = len(partition)
    max_part = max(partition)
    num_2s = sum(1 for p in partition if p == 2)

    # Product of transitive group counts
    combo_count = 1
    for p in partition:
        combo_count *= NR_TRANSITIVE.get(p, max(1, p))

    # Symmetry discount for repeated parts
    for cnt in Counter(partition).values():
        if cnt > 1:
            factorial = 1
            for i in range(2, cnt + 1):
                factorial *= i
            combo_count = max(1, combo_count // factorial)

    # Base cost per combo
    if max_part >= 8:
        base_cost_per_combo = max_part * 0.8
    else:
        base_cost_per_combo = max_part * 0.3

    # C2 optimization discount
    if num_2s >= 2:
        base_cost_per_combo *= 0.3

    # Goursat discount for 2-part partitions
    if k == 2 and max_part >= 5:
        base_cost_per_combo *= 0.3

    cost = combo_count * base_cost_per_combo

    return max(0.1, cost)


# ===========================================================================
# Spot-check values (known-good from consistent previous runs)
# ===========================================================================
SPOT_CHECK = {
    (16,):     1954,
    (14, 2):   134,
    (13, 3):   26,
    (12, 4):   8167,
}


# ===========================================================================
# Manifest management
# ===========================================================================
def create_manifest(partitions, assignments):
    """Create initial manifest tracking per-partition status."""
    manifest = {
        "n": N,
        "inherited": INHERITED_FROM_S15,
        "expected_fpf": EXPECTED_FPF,
        "expected_total": OEIS_S16,
        "created": datetime.datetime.now().isoformat(),
        "partitions": {},
    }
    for worker_id, worker_parts in enumerate(assignments):
        for p in worker_parts:
            key = partition_key(p)
            manifest["partitions"][key] = {
                "partition": list(p),
                "status": "pending",
                "worker_id": worker_id,
                "fpf_count": None,
                "elapsed_s": None,
                "started_at": None,
                "completed_at": None,
            }
    return manifest


def load_manifest():
    """Load manifest from disk, or return None if not found."""
    if not os.path.exists(MANIFEST_FILE):
        return None
    with open(MANIFEST_FILE, "r") as f:
        return json.load(f)


def save_manifest(manifest):
    """Save manifest atomically (write to temp, then rename)."""
    tmp = MANIFEST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    if os.path.exists(MANIFEST_FILE):
        os.replace(tmp, MANIFEST_FILE)
    else:
        os.rename(tmp, MANIFEST_FILE)


def update_manifest_partition(manifest, partition_key_str, **kwargs):
    """Update fields for a single partition in the manifest."""
    if partition_key_str in manifest["partitions"]:
        manifest["partitions"][partition_key_str].update(kwargs)
        save_manifest(manifest)


# ===========================================================================
# Worker assignment (LPT scheduling)
# ===========================================================================
def assign_partitions_to_workers(partitions, num_workers, ckpt_progress=None):
    """Assign partitions to workers using LPT (Longest Processing Time) scheduling.

    If ckpt_progress is provided, adjust costs based on checkpoint recovery
    (fraction of combos already completed).
    """
    costs = []
    for p in partitions:
        est = estimate_partition_cost(p)
        pt = tuple(p)
        if ckpt_progress and pt in ckpt_progress:
            done_combos, _, total_combos = ckpt_progress[pt]
            frac_remaining = max(0.01, 1.0 - done_combos / total_combos) if total_combos > 0 else 1.0
            est *= frac_remaining
        costs.append((est, p))
    costs.sort(reverse=True)

    workers = [[] for _ in range(num_workers)]
    worker_loads = [0.0] * num_workers

    for cost, partition in costs:
        min_idx = worker_loads.index(min(worker_loads))
        workers[min_idx].append(partition)
        worker_loads[min_idx] += cost

    return workers, worker_loads


def print_assignment(workers, worker_loads, partitions):
    """Print partition assignment table."""
    print(f"\nPartition assignment ({len(partitions)} partitions -> {len(workers)} workers):")
    print("-" * 80)
    for i, (parts, load) in enumerate(zip(workers, worker_loads)):
        if not parts:
            continue
        print(f"  Worker {i}: {len(parts)} partitions, est. {load:.0f}s ({load/3600:.1f}h)")
        for ps in parts[:8]:
            est = estimate_partition_cost(ps)
            print(f"    {str(list(ps)):30s}  est. {est:.0f}s ({est/3600:.1f}h)")
        if len(parts) > 8:
            rest_cost = sum(estimate_partition_cost(ps) for ps in parts[8:])
            print(f"    ... and {len(parts)-8} more (est. {rest_cost:.0f}s)")
    print("-" * 80)
    total_est = sum(estimate_partition_cost(p) for p in partitions)
    max_load = max(worker_loads) if worker_loads else 0
    print(f"  Total CPU est:   {total_est:.0f}s ({total_est/3600:.1f}h)")
    print(f"  Max worker est:  {max_load:.0f}s ({max_load/3600:.1f}h)")
    print(f"  Expected FPF:    {EXPECTED_FPF}")
    print(f"  Expected total:  {OEIS_S16}")


# ===========================================================================
# GAP worker script generation
# ===========================================================================
def create_worker_gap_script(partitions, worker_id, output_dir):
    """Create a GAP script that processes partitions and saves generators."""
    log_file = os.path.join(output_dir, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(output_dir, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(output_dir, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    heartbeat_file = os.path.join(output_dir, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")

    partition_strs = []
    for p in partitions:
        partition_strs.append("[" + ",".join(str(x) for x in p) + "]")
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(partitions)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S15)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Enable heartbeat
_HEARTBEAT_FILE := "{heartbeat_file}";

# Clear H1 cache initially to avoid stale entries from previous runs
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\n========================================\\n");
    Print("Partition ", part, ":\\n");
    partStart := Runtime();

    # Write heartbeat before starting partition
    PrintTo("{heartbeat_file}",
        "starting partition ", part, "\\n");

    fpf_classes := FindFPFClassesForPartition({N}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    # Save generators to per-partition file
    partStr := JoinStringsWithSeparator(List(part, String), "_");
    genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
    PrintTo(genFile, "");  # Clear any previous content
    for _h_idx in [1..Length(fpf_classes)] do
        _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                      g -> ListPerm(g, {N}));
        AppendTo(genFile, String(_gens), "\\n");
    od;
    Print("  Generators saved to ", genFile, "\\n");

    # Write count to results file
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");

    # Memory stats
    if IsBound(GasmanStatistics) then
        Print("  Memory: ", GasmanStatistics(), "\\n");
    fi;

    # Clear runtime caches between partitions to free memory
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    # Write heartbeat after completing partition
    PrintTo("{heartbeat_file}",
        "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {worker_id} complete: ", totalCount, " total classes in ",
      workerTime, "s\\n");

# Write final summary
AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

# Save FPF cache for future use
if IsBound(SaveFPFSubdirectCache) then
    SaveFPFSubdirectCache();
fi;

LogTo();
QUIT;
'''

    script_file = os.path.join(output_dir, f"worker_{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)

    return script_file


# ===========================================================================
# Worker process management
# ===========================================================================
def launch_gap_worker(script_file, worker_id):
    """Launch a GAP worker process, return Popen object."""
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME
    )
    return process


def read_heartbeat(worker_id, output_dir):
    """Read heartbeat file for a worker. Returns (content, mtime) or (None, None)."""
    hb_file = os.path.join(output_dir, f"worker_{worker_id}_heartbeat.txt")
    try:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            with open(hb_file, "r") as f:
                content = f.read().strip()
            return content, mtime
    except (OSError, IOError):
        pass
    return None, None


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
                pass  # Use partition counts instead
            elif line.startswith("TIME"):
                worker_time = float(line.split()[1])
            elif line:
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    part_str = parts[0].strip()
                    count = int(parts[1])
                    partition_counts[part_str] = count
                    total += count

    return partition_counts, total, worker_time


def get_completed_partitions_from_results(output_dir, max_workers):
    """Scan all worker result files for completed partitions."""
    completed = {}
    for wid in range(max_workers):
        result_file = os.path.join(output_dir, f"worker_{wid}_results.txt")
        if not os.path.exists(result_file):
            continue
        with open(result_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOTAL") or line.startswith("TIME") or not line:
                    continue
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    part_str = parts[0].strip()
                    count = int(parts[1])
                    try:
                        p = ast.literal_eval(part_str.replace(" ", ""))
                        key = partition_key(p)
                        completed[key] = count
                    except (ValueError, SyntaxError):
                        pass
    return completed


# ===========================================================================
# Main runner with poll loop
# ===========================================================================
def log_msg(msg, also_print=True):
    """Log a message to master log and optionally print."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if also_print:
        print(line)
    try:
        with open(MASTER_LOG, "a") as f:
            f.write(line + "\n")
    except (OSError, IOError):
        pass


def run_workers(manifest, active_assignments, timeout):
    """Launch workers and monitor with poll loop."""
    processes = {}
    start_times = {}
    assignment_dict = {}

    for worker_id, parts in active_assignments:
        script = create_worker_gap_script(parts, worker_id, OUTPUT_DIR)
        proc = launch_gap_worker(script, worker_id)
        processes[worker_id] = proc
        start_times[worker_id] = time.time()
        assignment_dict[worker_id] = parts

        # Mark all partitions as running
        for p in parts:
            key = partition_key(p)
            update_manifest_partition(
                manifest, key,
                status="running",
                worker_id=worker_id,
                started_at=datetime.datetime.now().isoformat()
            )

        log_msg(f"Worker {worker_id} launched (PID {proc.pid}), "
                f"{len(parts)} partitions: "
                f"{', '.join(str(list(p)) for p in parts[:3])}"
                f"{'...' if len(parts) > 3 else ''}")

    overall_start = time.time()
    completed_workers = set()
    last_progress_time = time.time()

    # Poll loop
    while len(completed_workers) < len(processes):
        time.sleep(30)
        now = time.time()

        for worker_id, proc in processes.items():
            if worker_id in completed_workers:
                continue

            rc = proc.poll()
            elapsed = now - start_times[worker_id]

            if rc is not None:
                # Worker finished
                completed_workers.add(worker_id)
                if rc == 0:
                    log_msg(f"Worker {worker_id} completed (rc=0) in {elapsed:.0f}s "
                            f"({elapsed/3600:.1f}h)")
                else:
                    log_msg(f"Worker {worker_id} FAILED (rc={rc}) after {elapsed:.0f}s")
                    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log")
                    if os.path.exists(log_file):
                        with open(log_file, "r", errors="replace") as lf:
                            log_tail = lf.readlines()[-5:]
                        log_msg(f"  Log tail: {''.join(log_tail)[:500]}")

                # Update manifest for this worker's partitions
                pc, total, wtime = parse_worker_results(worker_id, OUTPUT_DIR)
                for p in assignment_dict[worker_id]:
                    key = partition_key(p)
                    for rkey, count in pc.items():
                        try:
                            rp = ast.literal_eval(rkey.replace(" ", ""))
                            if tuple(rp) == tuple(p):
                                update_manifest_partition(
                                    manifest, key,
                                    status="completed" if rc == 0 else "failed",
                                    fpf_count=count,
                                    completed_at=datetime.datetime.now().isoformat()
                                )
                                break
                        except (ValueError, SyntaxError):
                            pass
                    else:
                        if rc != 0:
                            update_manifest_partition(manifest, key, status="failed")

            elif elapsed > timeout:
                log_msg(f"Worker {worker_id} TIMEOUT after {elapsed:.0f}s, killing")
                proc.kill()
                completed_workers.add(worker_id)
                for p in assignment_dict[worker_id]:
                    key = partition_key(p)
                    update_manifest_partition(manifest, key, status="failed")

            else:
                # Still running - check heartbeat
                hb_content, hb_mtime = read_heartbeat(worker_id, OUTPUT_DIR)
                if hb_mtime is not None:
                    staleness = now - hb_mtime
                    if staleness > HEARTBEAT_STALE_THRESHOLD:
                        log_msg(f"  WARNING: Worker {worker_id} heartbeat stale "
                                f"({staleness:.0f}s ago): {hb_content}")

        # Progress line every 30s
        if now - last_progress_time >= 30:
            last_progress_time = now
            wall = now - overall_start
            n_done = len(completed_workers)
            n_total = len(processes)
            running_ids = [wid for wid in processes if wid not in completed_workers]

            # Count completed partitions from result files
            done_parts = 0
            fpf_so_far = 0
            for wid in range(max(processes.keys()) + 1):
                pc, total, _ = parse_worker_results(wid, OUTPUT_DIR)
                done_parts += len(pc)
                fpf_so_far += total

            total_parts = len(manifest["partitions"])

            status_parts = []
            for wid in running_ids[:4]:
                hb, _ = read_heartbeat(wid, OUTPUT_DIR)
                if hb:
                    status_parts.append(f"W{wid}:{hb[:40]}")
                else:
                    status_parts.append(f"W{wid}:running")

            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] "
                  f"Workers: {n_done}/{n_total} done | "
                  f"Partitions: {done_parts}/{total_parts} | "
                  f"FPF: {fpf_so_far} | "
                  f"Wall: {wall/3600:.1f}h | "
                  f"{' | '.join(status_parts)}")

    overall_elapsed = time.time() - overall_start
    log_msg(f"All workers finished in {overall_elapsed:.0f}s ({overall_elapsed/3600:.1f}h)")
    return overall_elapsed


# ===========================================================================
# Result collection
# ===========================================================================
def collect_all_results(max_worker_id):
    """Collect and sum results from all worker output files."""
    total_fpf = 0
    partition_counts = {}
    worker_times = []

    for wid in range(max_worker_id + 1):
        pc, total, wtime = parse_worker_results(wid, OUTPUT_DIR)
        partition_counts.update(pc)
        total_fpf += total
        if wtime > 0:
            worker_times.append((wid, wtime))

    return total_fpf, partition_counts, worker_times


# ===========================================================================
# Combine results into s16_subgroups.g
# ===========================================================================
def join_gap_continuation_lines(filepath):
    """Read a file and join GAP's backslash-continuation lines."""
    with open(filepath, "r") as f:
        raw_lines = f.readlines()

    joined = []
    current = ""
    for raw_line in raw_lines:
        line = raw_line.rstrip("\n").rstrip("\r")
        if line.endswith("\\"):
            current += line[:-1]
        else:
            current += line
            if current.strip():
                joined.append(current)
            current = ""
    if current.strip():
        joined.append(current)
    return joined


def parse_partition_gens(gens_dir):
    """Parse all per-partition generator files. Returns list of generator lists."""
    all_subgroups = []
    gens_path = Path(gens_dir)

    if not gens_path.exists():
        print(f"WARNING: gens directory {gens_dir} does not exist")
        return []

    for gen_file in sorted(gens_path.glob("gens_*.txt")):
        count = 0
        lines = join_gap_continuation_lines(gen_file)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                gens = ast.literal_eval(line)
                all_subgroups.append(gens)
                count += 1
            except (ValueError, SyntaxError) as e:
                print(f"  WARNING: Failed to parse line in {gen_file.name}: {e}")
                print(f"    Line preview: {line[:100]}...")
        print(f"  {gen_file.name}: {count} subgroups")

    return all_subgroups


def parse_inherited_chunked(filepath):
    """Parse s15_subgroups.g into list of generator image lists using chunked parsing."""
    print(f"  Parsing {filepath} (chunked)...")
    subgroups = []

    with open(filepath, "r") as f:
        content = f.read()

    # Remove backslash continuations
    content = content.replace("\\\n", "")

    # Strip comment lines and find the return statement
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            continue
        lines.append(line)
    text = "\n".join(lines)

    # Remove 'return' and trailing ';'
    text = text.strip()
    if text.startswith("return"):
        text = text[6:].strip()
    if text.endswith(";"):
        text = text[:-1].strip()

    # Parse entry by entry
    depth = 0
    current = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "[":
            if depth == 0:
                current = ch
            else:
                current += ch
            depth += 1
        elif ch == "]":
            depth -= 1
            current += ch
            if depth == 0:
                try:
                    sg = ast.literal_eval(current.strip())
                    subgroups.append(sg)
                except (ValueError, SyntaxError):
                    pass
                current = ""
                if len(subgroups) % 20000 == 0:
                    print(f"    ...parsed {len(subgroups)} subgroups")
        elif depth > 0:
            current += ch
        i += 1

    return subgroups


def write_subgroups_file(filepath, all_subgroups, n):
    """Write subgroups in the s14_subgroups.g format."""
    now = datetime.datetime.now()
    with open(filepath, "w") as f:
        f.write(f"# Conjugacy class representatives for S{n}\n")
        f.write(f"# Computed via Holt's algorithm with chief series lifting\n")
        f.write(f"# Computed: {now}\n")
        f.write(f"# Total: {len(all_subgroups)} conjugacy classes\n")
        f.write("return [\n")
        for i, gens in enumerate(all_subgroups):
            gen_strs = []
            for gen in gens:
                gen_str = "[ " + ", ".join(str(x) for x in gen) + " ]"
                gen_strs.append(gen_str)

            if len(gen_strs) == 1:
                entry = "  [ " + gen_strs[0] + " ]"
            else:
                entry = "  [ " + gen_strs[0] + ", \n"
                for j in range(1, len(gen_strs)):
                    if j < len(gen_strs) - 1:
                        entry += "  " + gen_strs[j] + ", \n"
                    else:
                        entry += "  " + gen_strs[j] + " ]"

            if i < len(all_subgroups) - 1:
                entry += ","
            f.write(entry + "\n")

            if (i + 1) % 50000 == 0:
                print(f"    ...written {i + 1}/{len(all_subgroups)}")

        f.write("];\n")


def combine_results():
    """Combine inherited S15 classes + FPF partition classes into s16_subgroups.g."""
    s15_file = os.path.join(CONJUGACY_CACHE, "s15_subgroups.g")
    s16_file = os.path.join(CONJUGACY_CACHE, "s16_subgroups.g")

    print(f"\nCombining results into {s16_file}...")

    # Step 1: Parse inherited S15 classes
    print(f"  Step 1: Parsing inherited S15 classes from {s15_file}...")
    inherited = parse_inherited_chunked(s15_file)
    print(f"  Loaded {len(inherited)} inherited classes")

    if len(inherited) != INHERITED_FROM_S15:
        print(f"  WARNING: Expected {INHERITED_FROM_S15} inherited classes, got {len(inherited)}")

    # Step 2: Extend inherited generators to degree 16 (add fixed point 16)
    print(f"  Step 2: Extending inherited generators to degree {N}...")
    for sg in inherited:
        for gen in sg:
            gen.append(N)

    # Step 3: Parse FPF partition generators
    print(f"  Step 3: Parsing FPF partition generators from {GENS_DIR}...")
    fpf_subgroups = parse_partition_gens(GENS_DIR)
    print(f"  Loaded {len(fpf_subgroups)} FPF classes")

    # Step 4: Combine
    all_subgroups = inherited + fpf_subgroups
    total = len(all_subgroups)
    print(f"  Step 4: Total = {len(inherited)} inherited + {len(fpf_subgroups)} FPF = {total}")

    if total == OEIS_S16:
        print(f"  MATCH: Total {total} == OEIS A000638(16) = {OEIS_S16}")
    else:
        print(f"  MISMATCH: Total {total} != OEIS A000638(16) = {OEIS_S16} (diff: {total - OEIS_S16})")

    # Step 5: Write output
    print(f"  Step 5: Writing {s16_file}...")
    write_subgroups_file(s16_file, all_subgroups, N)
    print(f"  Done! Output: {s16_file}")
    print(f"  File size: {os.path.getsize(s16_file) / 1024 / 1024:.1f} MB")

    return total


# ===========================================================================
# Resume logic
# ===========================================================================
def get_incomplete_partitions(manifest):
    """Get list of partitions that are not completed."""
    incomplete = []
    for key, info in manifest["partitions"].items():
        if info["status"] != "completed":
            incomplete.append(tuple(info["partition"]))
    return incomplete


def _estimate_total_combos(partition):
    """Estimate total combos for a partition based on NrTransitiveGroups and symmetry.

    For repeated parts of degree d with t = NrTransitiveGroups(d), the iteration
    picks indices i1 <= i2 <= ... <= ik, giving C(t+k-1, k) = (t+k-1)!/(k!(t-1)!)
    combinations. For distinct parts, it's just the product of NrTransitiveGroups.
    """
    from math import comb
    combo = 1
    counts = Counter(partition)
    for d, k in counts.items():
        t = NR_TRANSITIVE.get(d, max(1, d))
        if k == 1:
            combo *= t
        else:
            # Combinations with repetition: C(t+k-1, k)
            combo *= comb(t + k - 1, k)
    return max(1, combo)


def _scan_checkpoint_progress(incomplete_partitions):
    """Scan checkpoint dirs for existing .log files to estimate progress.

    Returns dict: partition_tuple -> (done_combos, total_fpf, estimated_total_combos)
    """
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    if not os.path.exists(ckpt_base):
        return {}

    progress = {}
    for p in incomplete_partitions:
        pt = tuple(p)
        partStr = "_".join(str(x) for x in pt)
        log_name = f"ckpt_16_{partStr}.log"

        best_combos = 0
        best_fpf = 0
        for entry in os.listdir(ckpt_base):
            candidate = os.path.join(ckpt_base, entry, log_name)
            if not os.path.exists(candidate):
                continue
            try:
                combos = 0
                fpf = 0
                with open(candidate, "r", errors="replace") as f:
                    for line in f:
                        if line.startswith("# end combo"):
                            combos += 1
                            # Extract total fpf from "# end combo (NNNN total fpf)"
                            m = re.search(r'\((\d+) total fpf\)', line)
                            if m:
                                fpf = int(m.group(1))
                if combos > best_combos:
                    best_combos = combos
                    best_fpf = fpf
            except (OSError, IOError):
                continue

        if best_combos > 0:
            total_combos = _estimate_total_combos(pt)
            progress[pt] = (best_combos, best_fpf, total_combos)

    return progress


def resume_computation(args):
    """Resume computation from manifest, redistributing incomplete partitions."""
    manifest = load_manifest()
    if manifest is None:
        print("ERROR: No manifest found. Run without --resume first.")
        sys.exit(1)

    # Scan result files for completed partitions
    completed = get_completed_partitions_from_results(OUTPUT_DIR, 32)

    # Update manifest
    for key, count in completed.items():
        if key in manifest["partitions"]:
            manifest["partitions"][key]["status"] = "completed"
            manifest["partitions"][key]["fpf_count"] = count
    save_manifest(manifest)

    incomplete = get_incomplete_partitions(manifest)
    fpf_so_far = sum(v for v in completed.values())
    print(f"\nResume: {len(completed)} completed ({fpf_so_far} FPF), {len(incomplete)} incomplete")

    if not incomplete:
        print("All partitions completed! Use --combine-only to assemble.")
        return

    # If specific partitions requested
    if args.resume_partitions:
        requested = set()
        for p_str in args.resume_partitions:
            try:
                p = tuple(ast.literal_eval(p_str))
                requested.add(p)
            except (ValueError, SyntaxError):
                print(f"ERROR: Cannot parse partition '{p_str}'")
                sys.exit(1)
        incomplete = [p for p in incomplete if p in requested]
        if not incomplete:
            print("No matching incomplete partitions found.")
            return

    # Scan for checkpoint logs to estimate remaining work
    ckpt_progress = _scan_checkpoint_progress(incomplete)

    print(f"Resuming {len(incomplete)} partitions with {args.workers} workers")
    for p in incomplete:
        pt = tuple(p)
        est = estimate_partition_cost(p)
        if pt in ckpt_progress:
            done_combos, total_fpf, total_combos = ckpt_progress[pt]
            frac_remaining = max(0.01, 1.0 - done_combos / total_combos) if total_combos > 0 else 1.0
            adj_est = est * frac_remaining
            print(f"  {str(list(p)):30s}  est. {adj_est:.0f}s ({adj_est/3600:.1f}h)"
                  f"  [ckpt: {done_combos}/{total_combos} combos, {total_fpf} fpf]")
        else:
            print(f"  {str(list(p)):30s}  est. {est:.0f}s ({est/3600:.1f}h)")

    # Reassign to fresh workers
    existing_workers = set()
    for info in manifest["partitions"].values():
        if info.get("worker_id") is not None:
            existing_workers.add(info["worker_id"])
    next_worker_id = max(existing_workers) + 1 if existing_workers else 0

    # Use checkpoint-adjusted costs for LPT scheduling
    assignments, loads = assign_partitions_to_workers(
        incomplete, args.workers, ckpt_progress=ckpt_progress)
    print_assignment(assignments, loads, incomplete)

    if args.dry_run:
        print("\n[DRY RUN] Would resume with the above assignment.")
        return

    # Remap worker IDs
    active_assignments = []
    for i, parts in enumerate(assignments):
        if parts:
            wid = next_worker_id + i
            active_assignments.append((wid, parts))
            os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}"),
                       exist_ok=True)

    # Recover checkpoint logs from previous workers.
    # For each incomplete partition, find the best .log file (most combos)
    # across all old worker checkpoint dirs, and copy it to the new worker's dir.
    _recover_checkpoint_logs(incomplete, active_assignments, next_worker_id)

    run_workers(manifest, active_assignments, args.timeout)
    print_final_results(next_worker_id + args.workers)


def _recover_checkpoint_logs(incomplete_partitions, active_assignments, next_worker_id):
    """Copy best existing checkpoint .log files to new worker checkpoint dirs."""
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")

    # Build map: partition -> new worker checkpoint dir
    part_to_new_dir = {}
    for wid, parts in active_assignments:
        for p in parts:
            part_to_new_dir[tuple(p)] = os.path.join(ckpt_base, f"worker_{wid}")

    # Scan all existing worker checkpoint dirs for .log files
    recovered = 0
    for p in incomplete_partitions:
        pt = tuple(p)
        if pt not in part_to_new_dir:
            continue
        partStr = "_".join(str(x) for x in pt)
        log_name = f"ckpt_16_{partStr}.log"
        new_dir = part_to_new_dir[pt]
        new_log = os.path.join(new_dir, log_name)

        # Skip if the new dir already has this log (shouldn't happen with fresh dirs)
        if os.path.exists(new_log) and os.path.getsize(new_log) > 0:
            continue

        # Find best .log across all old worker dirs
        best_log = None
        best_combos = 0
        for entry in os.listdir(ckpt_base):
            old_dir = os.path.join(ckpt_base, entry)
            if not os.path.isdir(old_dir):
                continue
            # Skip new worker dirs
            try:
                old_wid = int(entry.replace("worker_", ""))
                if old_wid >= next_worker_id:
                    continue
            except ValueError:
                continue
            candidate = os.path.join(old_dir, log_name)
            if not os.path.exists(candidate):
                continue
            # Count combos via "# end combo" lines
            try:
                with open(candidate, "r", errors="replace") as f:
                    combo_count = sum(1 for line in f if line.startswith("# end combo"))
                if combo_count > best_combos:
                    best_combos = combo_count
                    best_log = candidate
            except (OSError, IOError):
                continue

        if best_log and best_combos > 0:
            shutil.copy2(best_log, new_log)
            print(f"  RECOVER: {list(pt)} - copied {best_combos} combos from {os.path.basename(os.path.dirname(best_log))}")
            recovered += 1

    if recovered > 0:
        print(f"  Recovered checkpoint logs for {recovered} partitions")


# ===========================================================================
# Final result printing
# ===========================================================================
def print_final_results(max_worker_id):
    """Collect and print final results with spot-check validation."""
    total_fpf = 0
    partition_counts = {}
    worker_times = []

    for wid in range(max_worker_id + 1):
        pc, total, wtime = parse_worker_results(wid, OUTPUT_DIR)
        partition_counts.update(pc)
        total_fpf += total
        if wtime > 0:
            worker_times.append((wid, wtime))

    total = INHERITED_FROM_S15 + total_fpf
    print(f"\n{'='*70}")
    print(f"Results for S_{N}:")
    print(f"  Inherited from S_{N-1}: {INHERITED_FROM_S15}")
    print(f"  FPF partition classes:  {total_fpf}")
    print(f"  TOTAL:                  {total}")

    if total == OEIS_S16:
        print(f"  MATCH: {total} == OEIS A000638(16) = {OEIS_S16}")
    elif len(partition_counts) == 55:
        print(f"  MISMATCH: {total} != OEIS A000638(16) = {OEIS_S16} (diff: {total - OEIS_S16})")
    else:
        print(f"  ({len(partition_counts)}/55 partitions completed, target: {OEIS_S16})")

    # Spot checks
    print(f"\nSpot checks:")
    spot_ok = True
    for pt, expected in sorted(SPOT_CHECK.items()):
        # Find in partition_counts (GAP format)
        gap_str = "[ " + ", ".join(str(x) for x in pt) + " ]"
        found = None
        for rkey, count in partition_counts.items():
            try:
                rp = ast.literal_eval(rkey.replace(" ", ""))
                if tuple(rp) == pt:
                    found = count
                    break
            except (ValueError, SyntaxError):
                pass

        if found is not None:
            status = "OK" if found == expected else f"FAIL (expected {expected})"
            if found != expected:
                spot_ok = False
            print(f"  {str(list(pt)):20s}: {found:>6d}  {status}")
        else:
            print(f"  {str(list(pt)):20s}: not yet computed")

    if worker_times:
        times_only = [t for _, t in worker_times]
        print(f"\nTiming:")
        print(f"  Max worker CPU:   {max(times_only):.0f}s ({max(times_only)/3600:.1f}h)")
        print(f"  Sum worker CPU:   {sum(times_only):.0f}s ({sum(times_only)/3600:.1f}h)")

    if partition_counts:
        print(f"\nPer-partition counts ({len(partition_counts)} partitions):")
        # Sort by partition
        sorted_parts = []
        for part_str, count in partition_counts.items():
            try:
                rp = ast.literal_eval(part_str.replace(" ", ""))
                sorted_parts.append((tuple(rp), count))
            except (ValueError, SyntaxError):
                sorted_parts.append((part_str, count))
        sorted_parts.sort(key=lambda x: x[0] if isinstance(x[0], tuple) else (0,))
        for pt, count in sorted_parts:
            if isinstance(pt, tuple):
                print(f"  {str(list(pt)):30s}: {count}")
            else:
                print(f"  {pt:30s}: {count}")

    return total_fpf, partition_counts


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Fresh S16 conjugacy class computation (clean run)")
    parser.add_argument("--workers", type=int, default=8,
                       help="Number of parallel workers (default: 8)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show assignment without running")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Per-worker timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--combine-only", action="store_true",
                       help="Skip computation, just combine results")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from manifest, redistributing incomplete partitions")
    parser.add_argument("--resume-partitions", nargs="*", default=None,
                       help='Resume specific partitions only, e.g. "[8,8]" "[12,4]"')
    args = parser.parse_args()

    print(f"S{N} Conjugacy Class Computation (FRESH)")
    print("=" * 70)
    print(f"Inherited from S{N-1}: {INHERITED_FROM_S15}")
    print(f"OEIS target:  {OEIS_S16} (FPF = {EXPECTED_FPF})")
    print(f"Workers:      {args.workers}")
    print(f"Timeout:      {args.timeout}s ({args.timeout/3600:.1f}h) per worker")
    print(f"Output:       {OUTPUT_DIR}")

    if args.combine_only:
        total = combine_results()
        print(f"\nTo update database/lift_cache.g, add:")
        print(f'  LIFT_CACHE.("16") := {total};')
        return

    if args.resume or args.resume_partitions:
        resume_computation(args)
        return

    # Check for existing output dir
    if os.path.exists(OUTPUT_DIR):
        existing = get_completed_partitions_from_results(OUTPUT_DIR, 32)
        if existing:
            print(f"\nWARNING: {OUTPUT_DIR} already exists with {len(existing)} completed partitions.")
            print(f"Use --resume to continue, or delete the directory for a truly fresh start.")
            resp = input("Continue anyway and overwrite? [y/N] ")
            if resp.lower() != 'y':
                sys.exit(0)

    # Generate FPF partitions
    partitions = partitions_min_part(N)
    print(f"\nFPF partitions of {N}: {len(partitions)}")

    # Assign to workers
    assignments, loads = assign_partitions_to_workers(partitions, args.workers)
    print_assignment(assignments, loads, partitions)

    # Filter out empty workers
    active_assignments = [(i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active_assignments)
    print(f"\nActive workers: {num_active}")

    if args.dry_run:
        print("\n[DRY RUN] Would run with the above assignment.")
        return

    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GENS_DIR, exist_ok=True)
    for worker_id, _ in active_assignments:
        os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}"),
                   exist_ok=True)

    # Initialize master log
    with open(MASTER_LOG, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"S{N} FRESH computation started at {datetime.datetime.now().isoformat()}\n")
        f.write(f"Workers: {num_active}, Timeout: {args.timeout}s\n")
        f.write(f"Target: {OEIS_S16} (FPF = {EXPECTED_FPF})\n")
        f.write(f"{'='*70}\n")

    # Clear previous result files and gens files for active workers
    for worker_id, parts in active_assignments:
        result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)
        for p in parts:
            gen_file = os.path.join(GENS_DIR, f"gens_{partition_key(p)}.txt")
            if os.path.exists(gen_file):
                os.remove(gen_file)

    # Create manifest
    manifest = create_manifest(partitions, assignments)
    save_manifest(manifest)
    log_msg(f"Manifest created with {len(partitions)} partitions")

    # Launch and monitor
    log_msg(f"Launching {num_active} workers...")
    overall_elapsed = run_workers(manifest, active_assignments, args.timeout)

    # Final results
    total_fpf, partition_counts = print_final_results(args.workers)

    total = INHERITED_FROM_S15 + total_fpf
    log_msg(f"FINAL: S_{N} = {total} "
            f"({INHERITED_FROM_S15} inherited + {total_fpf} FPF)")
    log_msg(f"Wall-clock: {overall_elapsed:.0f}s ({overall_elapsed/3600:.1f}h)")

    if total == OEIS_S16:
        log_msg(f"SUCCESS: Matches OEIS A000638(16) = {OEIS_S16}")
    elif len(partition_counts) == 55:
        log_msg(f"MISMATCH: {total} != OEIS A000638(16) = {OEIS_S16}")

    # Check if all partitions completed
    n_completed = sum(1 for p in manifest["partitions"].values()
                     if p["status"] == "completed")
    n_total = len(manifest["partitions"])
    if n_completed < n_total:
        log_msg(f"WARNING: Only {n_completed}/{n_total} partitions completed. "
                f"Use --resume to retry failed partitions.")
    else:
        log_msg(f"All {n_total} partitions completed successfully!")
        print(f"\nRun 'python run_s16_fresh.py --combine-only' to assemble the final cache.")


if __name__ == "__main__":
    main()
