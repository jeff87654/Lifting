###############################################################################
# run_holt.py - Parallel partition processing via the Holt engine.
#
# Identical to run_parallel.py in orchestration (same partition sharding,
# same heartbeat format, same checkpoint semantics), but each GAP worker
# additionally loads holt_engine/loader.g and sets USE_HOLT_ENGINE := true.
# With that flag, the four call sites in lifting_method_fast_v2.g route
# through HoltSubgroupClassesOfProduct via _HoltDispatchLift.
#
# Usage:
#   python run_holt.py <n> [--workers N] [--dry-run]
#
# Example:
#   python run_holt.py 14 --workers 6
###############################################################################

import subprocess
import os
import sys
import time
import json
import re
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configuration
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_SCRIPT_PATH_PREFIX = "/cygdrive/c/Users/jeffr/Downloads/Lifting"

# S13 timing data for cost estimation (seconds)
S13_TIMING = {
    (13,): 0.03, (11,2): 9.6, (10,3): 230, (9,4): 173,
    (9,2,2): 17.8, (8,5): 222, (8,3,2): 198, (7,6): 116,
    (7,4,2): 52, (7,3,3): 23, (7,2,2,2): 1.7, (6,5,2): 88,
    (6,4,3): 340, (6,3,2,2): 74, (5,5,3): 34, (5,4,4): 425,
    (5,4,2,2): 150, (5,3,3,2): 40, (5,2,2,2,2): 4.4,
    (4,4,3,2): 200, (4,3,3,3): 59, (4,3,2,2,2): 100,
    (3,3,3,2,2): 7.3, (3,2,2,2,2,2): 5.4,
}


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


def estimate_partition_cost(partition):
    """Estimate cost of a partition based on S13 timing data and heuristics."""
    # Direct lookup for S13 partitions
    if tuple(partition) in S13_TIMING:
        return S13_TIMING[tuple(partition)]

    # Heuristic based on partition structure:
    # - More distinct large parts = more transitive groups to combine = slower
    # - Larger max part = larger groups = more lifting layers
    # - More trailing 2s = C2 optimization helps
    n = sum(partition)
    k = len(partition)
    max_part = max(partition)
    num_distinct = len(set(partition))
    num_2s = sum(1 for p in partition if p == 2)

    # Base cost scales with product of NrTransitiveGroups
    # NrTransitiveGroups grows roughly exponentially: 1,1,2,5,5,16,7,50,...
    nr_trans = {1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
                9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63}

    # Product of transitive group counts gives number of factor combinations
    combo_count = 1
    for p in partition:
        combo_count *= nr_trans.get(p, max(1, p))

    # Estimate: combo_count * base_lifting_cost_per_combo
    # Base cost per combo scales with max(partition) due to chief series length
    base_cost_per_combo = max_part * 0.5  # seconds, rough estimate

    # C2 optimization discount
    if num_2s >= 2:
        base_cost_per_combo *= 0.3

    cost = combo_count * base_cost_per_combo

    # Scale by degree relative to S13
    degree_scale = (n / 13.0) ** 2

    return max(0.1, cost * degree_scale)


def assign_partitions_to_workers(partitions, num_workers):
    """Assign partitions to workers using LPT (Longest Processing Time) scheduling.

    Assigns the most expensive partition to the least-loaded worker, ensuring
    good load balance.
    """
    # Sort partitions by estimated cost, descending
    costs = [(estimate_partition_cost(p), p) for p in partitions]
    costs.sort(reverse=True)

    # Initialize worker loads
    workers = [[] for _ in range(num_workers)]
    worker_loads = [0.0] * num_workers

    # LPT: assign each partition to the least-loaded worker
    for cost, partition in costs:
        min_idx = worker_loads.index(min(worker_loads))
        workers[min_idx].append(partition)
        worker_loads[min_idx] += cost

    # Print assignment summary
    print(f"\nPartition assignment ({len(partitions)} partitions -> {num_workers} workers):")
    for i, (parts, load) in enumerate(zip(workers, worker_loads)):
        part_strs = [str(list(p)) for p in parts]
        print(f"  Worker {i}: {len(parts)} partitions, est. {load:.0f}s")
        if len(parts) <= 5:
            for ps in part_strs:
                print(f"    {ps}")
        else:
            for ps in part_strs[:3]:
                print(f"    {ps}")
            print(f"    ... and {len(parts)-3} more")

    return workers


def create_worker_gap_script(n, partitions, worker_id, output_dir):
    """Create a GAP script for a single worker to process its assigned partitions."""
    log_file = os.path.join(output_dir, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt").replace("\\", "/")

    partition_strs = []
    for p in partitions:
        partition_strs.append("[" + ",".join(str(x) for x in p) + "]")
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting\\n");
Print("Processing {len(partitions)} partitions for S_{n}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load the Holt engine (defines _HoltDispatchLift + Holt* wrappers)
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

# Load precomputed caches
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear runtime caches for clean timing
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\nPartition ", part, ":\\n");
    partStart := Runtime();
    fpf_classes := HoltFPFClassesForPartition({n}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    # Write intermediate result
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {worker_id} complete: ", totalCount, " total classes in ", workerTime, "s\\n");

# Write final summary
AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

LogTo();
QUIT;
'''

    script_file = os.path.join(output_dir, f"worker_{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)

    return script_file


def run_gap_worker(script_file, worker_id, timeout=7200):
    """Run a single GAP worker process."""
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cygwin}"'
    ]

    start_time = time.time()
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=GAP_RUNTIME
        )
        stdout, stderr = process.communicate(timeout=timeout)
        elapsed = time.time() - start_time
        return {
            'worker_id': worker_id,
            'returncode': process.returncode,
            'elapsed': elapsed,
            'stdout': stdout,
            'stderr': stderr
        }
    except subprocess.TimeoutExpired:
        process.kill()
        return {
            'worker_id': worker_id,
            'returncode': -1,
            'elapsed': timeout,
            'stdout': '',
            'stderr': f'Timeout after {timeout}s'
        }
    except Exception as e:
        return {
            'worker_id': worker_id,
            'returncode': -2,
            'elapsed': time.time() - start_time,
            'stdout': '',
            'stderr': str(e)
        }


def collect_results(output_dir, num_workers):
    """Collect and sum results from all worker output files."""
    total_fpf = 0
    partition_counts = {}
    worker_times = []

    for worker_id in range(num_workers):
        result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
        if not os.path.exists(result_file):
            print(f"  WARNING: No results from worker {worker_id}")
            continue

        with open(result_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOTAL"):
                    worker_total = int(line.split()[1])
                elif line.startswith("TIME"):
                    worker_time = float(line.split()[1])
                    worker_times.append(worker_time)
                elif line:
                    # Parse "[ 5, 4, 3 ] 123" format
                    parts = line.rsplit(' ', 1)
                    if len(parts) == 2:
                        part_str = parts[0].strip()
                        count = int(parts[1])
                        partition_counts[part_str] = count
                        total_fpf += count

    return total_fpf, partition_counts, worker_times


def main():
    parser = argparse.ArgumentParser(description='Parallel S_n conjugacy class computation')
    parser.add_argument('n', type=int, help='Degree n for S_n')
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers')
    parser.add_argument('--dry-run', action='store_true', help='Show assignment without running')
    parser.add_argument('--timeout', type=int, default=7200, help='Per-worker timeout in seconds')
    args = parser.parse_args()

    n = args.n
    num_workers = args.workers

    # Known values for verification
    known = {1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296,
             9: 554, 10: 1593, 11: 3094, 12: 10723, 13: 20832, 14: 75154}

    print(f"Parallel S_{n} Computation")
    print(f"=" * 50)

    # Get inherited count from S_{n-1}
    if n - 1 in known:
        inherited = known[n - 1]
    else:
        print(f"ERROR: Need S_{n-1} count. Known values: {list(known.keys())}")
        sys.exit(1)

    print(f"Inherited from S_{n-1}: {inherited}")

    # Generate FPF partitions
    partitions = partitions_min_part(n)
    print(f"FPF partitions of {n}: {len(partitions)}")

    # Assign to workers
    assignments = assign_partitions_to_workers(partitions, num_workers)

    # Filter out empty workers
    active_workers = [(i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active_workers)
    print(f"\nActive workers: {num_active}")

    if args.dry_run:
        print("\n[DRY RUN] Would run with the above assignment.")
        return

    # Create output directory
    output_dir = os.path.join(LIFTING_DIR, f"parallel_s{n}")
    os.makedirs(output_dir, exist_ok=True)

    # Initialize result files (clear any previous)
    for worker_id, _ in active_workers:
        result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)

    # Create GAP scripts for each worker
    scripts = {}
    for worker_id, parts in active_workers:
        script_file = create_worker_gap_script(n, parts, worker_id, output_dir)
        scripts[worker_id] = script_file

    print(f"\nLaunching {num_active} workers...")
    overall_start = time.time()

    # Launch workers in parallel
    futures = {}
    with ProcessPoolExecutor(max_workers=num_active) as executor:
        for worker_id, _ in active_workers:
            future = executor.submit(run_gap_worker, scripts[worker_id], worker_id, args.timeout)
            futures[future] = worker_id

        # Collect results as they complete
        for future in as_completed(futures):
            worker_id = futures[future]
            result = future.result()
            elapsed = result['elapsed']
            rc = result['returncode']
            if rc == 0:
                print(f"  Worker {worker_id} completed in {elapsed:.1f}s")
            else:
                print(f"  Worker {worker_id} FAILED (rc={rc}) after {elapsed:.1f}s")
                if result['stderr']:
                    print(f"    stderr: {result['stderr'][:200]}")

    overall_elapsed = time.time() - overall_start
    print(f"\nAll workers finished in {overall_elapsed:.1f}s wall-clock")

    # Collect and sum results
    print(f"\nCollecting results...")
    total_fpf, partition_counts, worker_times = collect_results(output_dir, num_workers)

    total = inherited + total_fpf
    print(f"\nResults for S_{n}:")
    print(f"  Inherited from S_{n-1}: {inherited}")
    print(f"  FPF partition classes:  {total_fpf}")
    print(f"  TOTAL:                  {total}")

    if n in known:
        expected = known[n]
        if total == expected:
            print(f"  Status: PASS (matches OEIS A000638 = {expected})")
        else:
            print(f"  Status: FAIL (expected {expected}, got {total})")
            print(f"  Difference: {total - expected}")
    else:
        print(f"  (No known value for verification)")

    if worker_times:
        print(f"\nTiming:")
        print(f"  Wall-clock:       {overall_elapsed:.1f}s")
        print(f"  Max worker time:  {max(worker_times):.1f}s")
        print(f"  Sum worker times: {sum(worker_times):.1f}s")
        print(f"  Speedup:          {sum(worker_times)/overall_elapsed:.1f}x")

    # Print per-partition breakdown
    if partition_counts:
        print(f"\nPer-partition counts:")
        for part_str in sorted(partition_counts.keys()):
            print(f"  {part_str}: {partition_counts[part_str]}")


if __name__ == "__main__":
    main()
