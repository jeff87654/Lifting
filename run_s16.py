###############################################################################
# run_s16.py - Compute S16 conjugacy classes with parallel partition processing
#
# Distributes 55 FPF partitions of 16 across N GAP worker processes.
# Each worker saves subgroup generators to per-partition files.
# After completion, combines inherited S15 classes + FPF classes.
#
# Features over run_s15.py:
#   - Manifest-based crash recovery (--resume)
#   - Per-worker heartbeat monitoring
#   - S15 timing data for accurate cost estimation
#   - Adaptive checkpoint intervals
#   - Per-combo timing logs
#
# Usage:
#   python run_s16.py --workers 8 --dry-run          # Preview assignment
#   python run_s16.py --workers 8                     # Launch computation
#   python run_s16.py --resume --workers 8            # Resume incomplete
#   python run_s16.py --resume-partitions "[8,8]" "[12,4]" --workers 4
#   python run_s16.py --combine-only                  # Assemble final cache
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
import threading
import shutil
from pathlib import Path
from copy import deepcopy

# ===========================================================================
# Configuration
# ===========================================================================
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
CONJUGACY_CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
N = 16
INHERITED_FROM_S15 = 159129  # OEIS A000638(15)

# NrTransitiveGroups for degrees 1..16
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954,
}

# S15 timing data for cost estimation (seconds, from actual S15 runs)
# These are the best baseline for S16 since they're only 1 degree below.
S15_TIMING = {
    (15,): 0.1, (13, 2): 13, (12, 3): 38, (11, 4): 28,
    (11, 2, 2): 23, (10, 5): 180, (10, 3, 2): 90,
    (9, 6): 200, (9, 4, 2): 120, (9, 3, 3): 45, (9, 2, 2, 2): 35,
    (8, 7): 250, (8, 5, 2): 200, (8, 4, 3): 400, (8, 3, 2, 2): 180,
    (7, 6, 2): 150, (7, 5, 3): 180, (7, 4, 4): 250,
    (7, 4, 2, 2): 100, (7, 3, 3, 2): 80, (7, 2, 2, 2, 2): 8,
    (6, 6, 3): 200, (6, 5, 4): 350, (6, 5, 2, 2): 120,
    (6, 4, 3, 2): 300, (6, 3, 3, 3): 100, (6, 3, 2, 2, 2): 80,
    (5, 5, 5): 60, (5, 5, 3, 2): 80, (5, 4, 4, 2): 350,
    (5, 4, 3, 3): 200, (5, 4, 2, 2, 2): 100, (5, 3, 3, 2, 2): 50,
    (5, 2, 2, 2, 2, 2): 10, (4, 4, 4, 3): 200,
    (4, 4, 3, 2, 2): 120, (4, 3, 3, 3, 2): 80, (4, 3, 2, 2, 2, 2): 60,
    (3, 3, 3, 3, 3): 15, (3, 3, 3, 2, 2, 2): 12, (3, 2, 2, 2, 2, 2, 2): 8,
}

# S13 timing data (fallback for parts that match S13 partitions)
S13_TIMING = {
    (13,): 0.03, (11, 2): 9.6, (10, 3): 26, (9, 4): 173,
    (9, 2, 2): 17.8, (8, 5): 133, (8, 3, 2): 90, (7, 6): 116,
    (7, 4, 2): 52, (7, 3, 3): 23, (7, 2, 2, 2): 1.7, (6, 5, 2): 88,
    (6, 4, 3): 181, (6, 3, 2, 2): 74, (5, 5, 3): 34, (5, 4, 4): 216,
    (5, 4, 2, 2): 150, (5, 3, 3, 2): 40, (5, 2, 2, 2, 2): 4.4,
    (4, 4, 3, 2): 84, (4, 3, 3, 3): 59, (4, 3, 2, 2, 2): 100,
    (3, 3, 3, 2, 2): 7.3, (3, 2, 2, 2, 2, 2): 5.4,
}

# Default timeout per worker: 12 hours
DEFAULT_TIMEOUT = 43200
# Heartbeat staleness threshold (seconds)
HEARTBEAT_STALE_THRESHOLD = 600  # 10 minutes

OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")
MASTER_LOG = os.path.join(OUTPUT_DIR, "run_s16.log")


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
    """Estimate cost of a partition based on S15 timing data and heuristics.

    Uses S15 data as baseline when available, otherwise builds estimate from
    combo counts and degree scaling.
    """
    pt = tuple(partition)

    # Single-part partitions [n] are near-instant: just enumerate transitive groups
    # No lifting needed. Cost scales linearly with NrTransitiveGroups(n).
    if len(partition) == 1:
        nr = NR_TRANSITIVE.get(partition[0], 100)
        return max(0.1, nr * 0.005)  # ~0.005s per group for invariant+dedup

    # Direct lookup in S15 timing data (best baseline for S16)
    if pt in S15_TIMING:
        # Scale up slightly since degree 16 > 15
        return S15_TIMING[pt] * 1.5

    n = sum(partition)
    k = len(partition)
    max_part = max(partition)
    num_2s = sum(1 for p in partition if p == 2)

    # Product of transitive group counts gives number of factor combinations
    combo_count = 1
    for p in partition:
        combo_count *= NR_TRANSITIVE.get(p, max(1, p))

    # Symmetry discount for repeated parts: k equal parts divide by k!
    from collections import Counter
    for cnt in Counter(partition).values():
        if cnt > 1:
            factorial = 1
            for i in range(2, cnt + 1):
                factorial *= i
            combo_count = max(1, combo_count // factorial)

    # Base cost per combo scales with max(partition) due to chief series length
    # Weight large parts more heavily due to non-abelian simple chief factors
    if max_part >= 8:
        base_cost_per_combo = max_part * 0.8  # A_n chief factors are expensive
    else:
        base_cost_per_combo = max_part * 0.3

    # C2 optimization discount
    if num_2s >= 2:
        base_cost_per_combo *= 0.3

    cost = combo_count * base_cost_per_combo

    # Scale by degree relative to baseline
    degree_scale = (n / 15.0) ** 2.5

    return max(0.1, cost * degree_scale)


# ===========================================================================
# Manifest management
# ===========================================================================
def create_manifest(partitions, assignments):
    """Create initial manifest tracking per-partition status."""
    manifest = {
        "n": N,
        "inherited": INHERITED_FROM_S15,
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
    # On Windows, need to remove target first if it exists
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
def assign_partitions_to_workers(partitions, num_workers):
    """Assign partitions to workers using LPT (Longest Processing Time) scheduling."""
    costs = [(estimate_partition_cost(p), p) for p in partitions]
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
    print("-" * 70)
    for i, (parts, load) in enumerate(zip(workers, worker_loads)):
        if not parts:
            continue
        print(f"  Worker {i}: {len(parts)} partitions, est. {load:.0f}s ({load/3600:.1f}h)")
        for ps in parts[:6]:
            est = estimate_partition_cost(ps)
            print(f"    {str(list(ps)):30s}  est. {est:.0f}s")
        if len(parts) > 6:
            print(f"    ... and {len(parts)-6} more")
    print("-" * 70)
    total_est = sum(estimate_partition_cost(p) for p in partitions)
    max_load = max(worker_loads) if worker_loads else 0
    print(f"  Total CPU est:   {total_est:.0f}s ({total_est/3600:.1f}h)")
    print(f"  Max worker est:  {max_load:.0f}s ({max_load/3600:.1f}h)")


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
    """Launch a GAP worker process, return Popen object.

    Uses DEVNULL for stdout/stderr to avoid pipe deadlock.
    All output goes to LogTo() files and result files instead.
    """
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


def read_heartbeat(worker_id):
    """Read heartbeat file for a worker. Returns (content, mtime) or (None, None)."""
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


def parse_worker_results(worker_id):
    """Parse results from a worker's result file."""
    result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
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


def get_completed_partitions_from_results(output_dir, num_workers):
    """Scan all worker result files for completed partitions."""
    completed = {}
    for wid in range(num_workers):
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
                    # Parse partition from GAP format "[ 8, 8 ]"
                    part_str = parts[0].strip()
                    count = int(parts[1])
                    # Convert GAP list to partition key
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
    with open(MASTER_LOG, "a") as f:
        f.write(line + "\n")


def run_workers(manifest, active_assignments, timeout):
    """Launch workers and monitor with poll loop."""
    # Create scripts and launch processes
    processes = {}
    start_times = {}

    for worker_id, parts in active_assignments:
        script = create_worker_gap_script(parts, worker_id, OUTPUT_DIR)
        proc = launch_gap_worker(script, worker_id)
        processes[worker_id] = proc
        start_times[worker_id] = time.time()

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
                    # Check worker log for error details (stderr goes to DEVNULL)
                    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log")
                    if os.path.exists(log_file):
                        with open(log_file, "r", errors="replace") as lf:
                            log_tail = lf.readlines()[-5:]
                        log_msg(f"  Log tail: {''.join(log_tail)[:500]}")

                # Update manifest for this worker's partitions
                pc, total, wtime = parse_worker_results(worker_id)
                for p in dict(active_assignments)[worker_id]:
                    key = partition_key(p)
                    # Parse GAP format from results
                    gap_str = str(list(p)).replace(" ", "")
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
                # Timeout
                log_msg(f"Worker {worker_id} TIMEOUT after {elapsed:.0f}s, killing")
                proc.kill()
                completed_workers.add(worker_id)
                for p in dict(active_assignments)[worker_id]:
                    key = partition_key(p)
                    update_manifest_partition(manifest, key, status="failed")

            else:
                # Still running - check heartbeat
                hb_content, hb_mtime = read_heartbeat(worker_id)
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

            # Count completed partitions from manifest
            done_parts = sum(1 for p in manifest["partitions"].values()
                           if p["status"] == "completed")
            total_parts = len(manifest["partitions"])

            status_parts = []
            for wid in running_ids:
                hb, _ = read_heartbeat(wid)
                if hb:
                    status_parts.append(f"W{wid}:{hb[:40]}")
                else:
                    status_parts.append(f"W{wid}:running")

            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] "
                  f"Workers: {n_done}/{n_total} done | "
                  f"Partitions: {done_parts}/{total_parts} | "
                  f"Wall: {wall/3600:.1f}h | "
                  f"{' | '.join(status_parts[:4])}")

    overall_elapsed = time.time() - overall_start
    log_msg(f"All workers finished in {overall_elapsed:.0f}s ({overall_elapsed/3600:.1f}h)")
    return overall_elapsed


# ===========================================================================
# Result collection
# ===========================================================================
def collect_all_results(num_workers):
    """Collect and sum results from all worker output files."""
    total_fpf = 0
    partition_counts = {}
    worker_times = []

    for worker_id in range(num_workers):
        result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
        if not os.path.exists(result_file):
            continue

        with open(result_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOTAL"):
                    pass
                elif line.startswith("TIME"):
                    worker_time = float(line.split()[1])
                    worker_times.append((worker_id, worker_time))
                elif line:
                    parts = line.rsplit(" ", 1)
                    if len(parts) == 2:
                        part_str = parts[0].strip()
                        count = int(parts[1])
                        partition_counts[part_str] = count
                        total_fpf += count

    return total_fpf, partition_counts, worker_times


# ===========================================================================
# Combine results
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


def parse_inherited_chunked(filepath, degree):
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

    # Parse entry by entry (avoid loading entire list at once for large files)
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
    inherited = parse_inherited_chunked(s15_file, 15)
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


def resume_computation(args):
    """Resume computation from manifest, redistributing incomplete partitions."""
    manifest = load_manifest()
    if manifest is None:
        print("ERROR: No manifest found. Run without --resume first.")
        sys.exit(1)

    # Figure out what's already completed from result files
    completed = get_completed_partitions_from_results(OUTPUT_DIR, 32)  # scan up to 32 workers

    # Update manifest with any completed partitions found in result files
    for key, count in completed.items():
        if key in manifest["partitions"]:
            manifest["partitions"][key]["status"] = "completed"
            manifest["partitions"][key]["fpf_count"] = count
    save_manifest(manifest)

    incomplete = get_incomplete_partitions(manifest)
    print(f"\nResume: {len(completed)} completed, {len(incomplete)} incomplete")

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

    print(f"Resuming {len(incomplete)} partitions with {args.workers} workers")
    for p in incomplete:
        print(f"  {list(p)}")

    # Reassign to fresh workers (use worker IDs starting from max existing + 1)
    existing_workers = set()
    for info in manifest["partitions"].values():
        if info.get("worker_id") is not None:
            existing_workers.add(info["worker_id"])
    next_worker_id = max(existing_workers) + 1 if existing_workers else 0

    assignments, loads = assign_partitions_to_workers(incomplete, args.workers)
    print_assignment(assignments, loads, incomplete)

    if args.dry_run:
        print("\n[DRY RUN] Would resume with the above assignment.")
        return

    # Remap worker IDs to avoid collisions
    active_assignments = []
    for i, parts in enumerate(assignments):
        if parts:
            wid = next_worker_id + i
            active_assignments.append((wid, parts))
            # Create checkpoint dir
            os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}"),
                       exist_ok=True)

    run_workers(manifest, active_assignments, args.timeout)

    # Collect and print results
    print_final_results(args.workers + next_worker_id)


# ===========================================================================
# Final result printing
# ===========================================================================
def print_final_results(max_worker_id):
    """Collect and print final results."""
    total_fpf = 0
    partition_counts = {}
    worker_times = []

    for wid in range(max_worker_id + 1):
        pc, total, wtime = parse_worker_results(wid)
        partition_counts.update(pc)
        total_fpf += total
        if wtime > 0:
            worker_times.append((wid, wtime))

    total = INHERITED_FROM_S15 + total_fpf
    print(f"\nResults for S_{N}:")
    print(f"  Inherited from S_{N-1}: {INHERITED_FROM_S15}")
    print(f"  FPF partition classes:  {total_fpf}")
    print(f"  TOTAL:                  {total}")
    print(f"  (No known value for S16 - this would be a new result!)")

    if worker_times:
        times_only = [t for _, t in worker_times]
        print(f"\nTiming:")
        print(f"  Max worker CPU:   {max(times_only):.0f}s ({max(times_only)/3600:.1f}h)")
        print(f"  Sum worker CPU:   {sum(times_only):.0f}s ({sum(times_only)/3600:.1f}h)")

    if partition_counts:
        print(f"\nPer-partition counts ({len(partition_counts)} partitions):")
        for part_str in sorted(partition_counts.keys()):
            print(f"  {part_str}: {partition_counts[part_str]}")

    return total_fpf, partition_counts


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="Compute S16 conjugacy classes")
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

    print(f"S{N} Conjugacy Class Computation")
    print("=" * 70)
    print(f"Inherited from S{N-1}: {INHERITED_FROM_S15}")
    print(f"Workers:  {args.workers}")
    print(f"Timeout:  {args.timeout}s ({args.timeout/3600:.1f}h) per worker")
    print(f"Output:   {OUTPUT_DIR}")

    if args.combine_only:
        total = combine_results()
        # Update lift cache
        print(f"\nTo update database/lift_cache.g, add:")
        print(f'  LIFT_CACHE.("16") := {total};')
        return

    if args.resume or args.resume_partitions:
        resume_computation(args)
        return

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
        f.write(f"S{N} computation started at {datetime.datetime.now().isoformat()}\n")
        f.write(f"Workers: {num_active}, Timeout: {args.timeout}s\n")
        f.write(f"{'='*70}\n")

    # Clear previous result files for active workers
    for worker_id, _ in active_assignments:
        result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)

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

    # Check if all partitions completed
    n_completed = sum(1 for p in manifest["partitions"].values()
                     if p["status"] == "completed")
    n_total = len(manifest["partitions"])
    if n_completed < n_total:
        log_msg(f"WARNING: Only {n_completed}/{n_total} partitions completed. "
                f"Use --resume to retry failed partitions.")
    else:
        log_msg(f"All {n_total} partitions completed successfully!")
        print(f"\nRun 'python run_s16.py --combine-only' to assemble the final cache.")


if __name__ == "__main__":
    main()
