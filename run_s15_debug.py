###############################################################################
# run_s15_debug.py - Diagnose S15 undercounting by disabling suspect optimizations
#
# Runs all 41 FPF partitions of S15 with one optimization disabled at a time.
# Compares per-partition counts against the known (buggy) baseline.
# Reports which partitions changed and by how much.
#
# Usage:
#   python run_s15_debug.py --disable orbital     [--workers 8] [--partitions 8,4,3 6,4,3,2]
#   python run_s15_debug.py --disable nonsplit     [--workers 8]
#   python run_s15_debug.py --disable fpf_imposs   [--workers 8]
#   python run_s15_debug.py --results-only DIRNAME  (skip computation, just compare)
#
###############################################################################

import subprocess
import os
import sys
import time
import re
import argparse
import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configuration
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
N = 15
EXPECTED_FPF = 83975  # OEIS A000638(15) - A000638(14) = 159129 - 75154

# Known baseline per-partition counts from the buggy S15 computation
# Total = 83962 (13 short of expected 83975)
BASELINE = {
    (15,): 104,
    (13, 2): 14,
    (12, 3): 1515,
    (11, 4): 58,
    (11, 2, 2): 25,
    (10, 5): 493,
    (10, 3, 2): 595,
    (9, 6): 1658,
    (9, 4, 2): 1955,
    (9, 3, 3): 621,
    (9, 2, 2, 2): 501,
    (8, 7): 690,
    (8, 5, 2): 2855,
    (8, 4, 3): 11512,
    (8, 3, 2, 2): 4823,
    (7, 6, 2): 570,
    (7, 5, 3): 155,
    (7, 4, 4): 843,
    (7, 4, 2, 2): 603,
    (7, 3, 3, 2): 166,
    (7, 2, 2, 2, 2): 122,
    (6, 6, 3): 3246,
    (6, 5, 4): 3976,
    (6, 5, 2, 2): 1717,
    (6, 4, 3, 2): 10228,
    (6, 3, 3, 3): 1064,
    (6, 3, 2, 2, 2): 2289,
    (5, 5, 5): 155,
    (5, 5, 3, 2): 287,
    (5, 4, 4, 2): 4742,
    (5, 4, 3, 3): 995,
    (5, 4, 2, 2, 2): 1905,
    (5, 3, 3, 2, 2): 421,
    (5, 2, 2, 2, 2, 2): 257,
    (4, 4, 4, 3): 8680,
    (4, 4, 3, 2, 2): 9732,
    (4, 3, 3, 3, 2): 1280,
    (4, 3, 2, 2, 2, 2): 2413,
    (3, 3, 3, 3, 3): 142,
    (3, 3, 3, 2, 2, 2): 316,
    (3, 2, 2, 2, 2, 2, 2): 239,
}

BASELINE_TOTAL = sum(BASELINE.values())

# Largest 8 partitions by count (~70% of FPF total) - test these first for speed
PRIORITY_PARTITIONS = [
    (8, 4, 3),       # 11512
    (6, 4, 3, 2),    # 10228
    (4, 4, 3, 2, 2), # 9732
    (4, 4, 4, 3),    # 8680
    (8, 3, 2, 2),    # 4823
    (5, 4, 4, 2),    # 4742
    (6, 5, 4),       # 3976
    (6, 6, 3),       # 3246
]


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


def create_worker_gap_script(partitions, worker_id, output_dir, disable_flag):
    """Create a GAP script that processes partitions with one optimization disabled."""
    log_file = os.path.join(output_dir, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt").replace("\\", "/")

    partition_strs = []
    for p in partitions:
        partition_strs.append("[" + ",".join(str(x) for x in p) + "]")
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    # Build the disable command based on which optimization to disable
    if disable_flag == "orbital":
        disable_cmd = 'USE_H1_ORBITAL := false;'
    elif disable_flag == "nonsplit":
        disable_cmd = 'USE_NONSPLIT_TEST := false;'
    elif disable_flag == "fpf_imposs":
        disable_cmd = 'USE_FPF_IMPOSSIBILITY := false;'
    else:
        disable_cmd = '# No optimization disabled (baseline run)'

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting at ", StringTime(Runtime()), "\\n");
Print("Disable flag: {disable_flag}\\n");
Print("Processing {len(partitions)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S14)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# DISABLE the suspect optimization
{disable_cmd}
Print("After disable: USE_H1_ORBITAL=", USE_H1_ORBITAL, " USE_NONSPLIT_TEST=", USE_NONSPLIT_TEST, " USE_FPF_IMPOSSIBILITY=", USE_FPF_IMPOSSIBILITY, "\\n");

# Clear H1 cache to ensure clean computation (but keep FPF subdirect cache warm)
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\nPartition ", part, ":\\n");
    partStart := Runtime();

    fpf_classes := FindFPFClassesForPartition({N}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    # Write count to results file
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {worker_id} complete: ", totalCount, " total classes in ",
      workerTime, "s\\n");

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


def run_gap_worker(script_file, worker_id, timeout=21600):
    """Run a single GAP worker process."""
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
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


def estimate_partition_cost(partition):
    """Rough cost estimate for LPT scheduling."""
    # Based on S13 partition timing, scaled by partition structure
    n = sum(partition)
    k = len(partition)
    max_part = max(partition)

    nr_trans = {1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
                9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104}

    combo_count = 1
    for p in partition:
        combo_count *= nr_trans.get(p, max(1, p))

    base_cost = combo_count * max_part * 0.3
    num_2s = sum(1 for p in partition if p == 2)
    if num_2s >= 2:
        base_cost *= 0.3

    return max(0.1, base_cost * (n / 13.0) ** 2.5)


def assign_partitions_to_workers(partitions, num_workers):
    """Assign partitions to workers using LPT scheduling."""
    costs = [(estimate_partition_cost(p), p) for p in partitions]
    costs.sort(reverse=True)

    workers = [[] for _ in range(num_workers)]
    worker_loads = [0.0] * num_workers

    for cost, partition in costs:
        min_idx = worker_loads.index(min(worker_loads))
        workers[min_idx].append(partition)
        worker_loads[min_idx] += cost

    return workers, worker_loads


def collect_results(output_dir, num_workers):
    """Collect results from all worker output files."""
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
                    pass
                elif line.startswith("TIME"):
                    worker_time = float(line.split()[1])
                    worker_times.append(worker_time)
                elif line:
                    # Parse "[ 5, 4, 3 ] 123" format
                    parts = line.rsplit(' ', 1)
                    if len(parts) == 2:
                        part_str = parts[0].strip()
                        count = int(parts[1])
                        # Convert "[ 8, 4, 3 ]" to tuple (8, 4, 3)
                        nums = re.findall(r'\d+', part_str)
                        partition_key = tuple(int(x) for x in nums)
                        partition_counts[partition_key] = count

    return partition_counts, worker_times


def compare_results(new_counts, disable_flag):
    """Compare new counts against baseline and report differences."""
    print(f"\n{'='*70}")
    print(f"COMPARISON: {disable_flag} disabled vs baseline")
    print(f"{'='*70}")

    new_total = sum(new_counts.values())
    baseline_total = BASELINE_TOTAL

    print(f"\nBaseline FPF total:  {baseline_total}")
    print(f"New FPF total:       {new_total}")
    print(f"Difference:          {new_total - baseline_total:+d}")
    print(f"Expected FPF total:  {EXPECTED_FPF}")

    if new_total == EXPECTED_FPF:
        print(f"\n*** NEW TOTAL MATCHES EXPECTED! Disabling '{disable_flag}' FIXES the bug! ***")
    elif new_total == baseline_total:
        print(f"\n  No change - '{disable_flag}' is NOT the culprit.")
    else:
        print(f"\n  Total changed but doesn't match expected.")

    # Per-partition comparison
    changed = []
    missing_from_new = []

    for part in sorted(BASELINE.keys()):
        old_count = BASELINE[part]
        if part in new_counts:
            new_count = new_counts[part]
            if new_count != old_count:
                changed.append((part, old_count, new_count))
        else:
            missing_from_new.append(part)

    # Check for partitions in new but not in baseline
    extra = []
    for part in new_counts:
        if part not in BASELINE:
            extra.append((part, new_counts[part]))

    if changed:
        print(f"\nChanged partitions ({len(changed)}):")
        print(f"  {'Partition':<25} {'Baseline':>10} {'New':>10} {'Diff':>10}")
        print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
        total_diff = 0
        for part, old, new in changed:
            diff = new - old
            total_diff += diff
            print(f"  {str(list(part)):<25} {old:>10} {new:>10} {diff:>+10}")
        print(f"  {'TOTAL DIFF':<25} {'':>10} {'':>10} {total_diff:>+10}")
    else:
        print(f"\nNo partitions changed.")

    if missing_from_new:
        print(f"\nPartitions missing from new results ({len(missing_from_new)}):")
        for part in missing_from_new:
            print(f"  {list(part)} (baseline: {BASELINE[part]})")

    if extra:
        print(f"\nExtra partitions in new results:")
        for part, count in extra:
            print(f"  {list(part)}: {count}")

    return changed


def main():
    parser = argparse.ArgumentParser(
        description='Diagnose S15 undercounting by disabling suspect optimizations')
    parser.add_argument('--disable', choices=['orbital', 'nonsplit', 'fpf_imposs', 'none'],
                        required=True,
                        help='Which optimization to disable')
    parser.add_argument('--workers', type=int, default=8,
                        help='Number of parallel workers')
    parser.add_argument('--timeout', type=int, default=21600,
                        help='Per-worker timeout (default 6h)')
    parser.add_argument('--partitions', nargs='*', default=None,
                        help='Specific partitions to test (e.g., "8,4,3" "6,4,3,2"). '
                             'Default: all 41 FPF partitions.')
    parser.add_argument('--priority-only', action='store_true',
                        help='Only test the 8 largest partitions (~70%% of FPF total)')
    parser.add_argument('--results-only', type=str, default=None,
                        help='Skip computation, just compare results in given directory')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show assignment without running')
    args = parser.parse_args()

    # Determine which partitions to test
    if args.partitions:
        partitions = []
        for p_str in args.partitions:
            parts = tuple(int(x) for x in p_str.split(','))
            partitions.append(parts)
    elif args.priority_only:
        partitions = PRIORITY_PARTITIONS
    else:
        partitions = partitions_min_part(N)

    output_dir = os.path.join(LIFTING_DIR, f"debug_s{N}_{args.disable}")

    print(f"S{N} Debug: Disable '{args.disable}'")
    print(f"{'='*60}")
    print(f"Partitions: {len(partitions)}")
    print(f"Workers:    {args.workers}")
    print(f"Output:     {output_dir}")
    print(f"Baseline FPF total: {BASELINE_TOTAL} (expected: {EXPECTED_FPF}, deficit: {EXPECTED_FPF - BASELINE_TOTAL})")

    if args.results_only:
        # Just compare existing results
        result_dir = args.results_only
        print(f"\nReading results from: {result_dir}")
        new_counts, worker_times = collect_results(result_dir, 100)  # try up to 100 workers
        print(f"Found {len(new_counts)} partition counts")
        compare_results(new_counts, args.disable)
        return

    # Assign to workers
    assignments, worker_loads = assign_partitions_to_workers(partitions, args.workers)
    active_workers = [(i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active_workers)

    print(f"\nPartition assignment ({len(partitions)} partitions -> {num_active} workers):")
    for i, (wid, parts) in enumerate(active_workers):
        print(f"  Worker {wid}: {len(parts)} partitions, est. {worker_loads[wid]:.0f}s")
        for ps in parts[:3]:
            print(f"    {list(ps)}")
        if len(parts) > 3:
            print(f"    ... and {len(parts)-3} more")

    if args.dry_run:
        total_est = sum(estimate_partition_cost(p) for p in partitions)
        max_est = max(worker_loads[i] for i, _ in active_workers)
        print(f"\n[DRY RUN] Est. total CPU: {total_est:.0f}s, est. wall-clock: {max_est:.0f}s")
        return

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)

    # Clear previous result files
    for worker_id, _ in active_workers:
        result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)

    # Create GAP scripts
    scripts = {}
    for worker_id, parts in active_workers:
        script_file = create_worker_gap_script(parts, worker_id, output_dir, args.disable)
        scripts[worker_id] = script_file

    print(f"\nLaunching {num_active} workers at {datetime.datetime.now().strftime('%H:%M:%S')}...")
    overall_start = time.time()

    # Launch workers in parallel
    futures = {}
    with ProcessPoolExecutor(max_workers=num_active) as executor:
        for worker_id, _ in active_workers:
            future = executor.submit(run_gap_worker, scripts[worker_id],
                                     worker_id, args.timeout)
            futures[future] = worker_id

        for future in as_completed(futures):
            worker_id = futures[future]
            result = future.result()
            elapsed = result['elapsed']
            rc = result['returncode']
            ts = datetime.datetime.now().strftime('%H:%M:%S')
            if rc == 0:
                print(f"  [{ts}] Worker {worker_id} completed in {elapsed:.1f}s")
            else:
                print(f"  [{ts}] Worker {worker_id} FAILED (rc={rc}) after {elapsed:.1f}s")
                if result['stderr']:
                    print(f"    stderr: {result['stderr'][:300]}")

    overall_elapsed = time.time() - overall_start
    print(f"\nAll workers finished in {overall_elapsed:.1f}s wall-clock")

    # Collect and compare results
    new_counts, worker_times = collect_results(output_dir, args.workers)
    print(f"\nCollected {len(new_counts)} partition counts")

    if worker_times:
        print(f"Timing: wall={overall_elapsed:.1f}s, max_worker={max(worker_times):.1f}s, "
              f"sum_cpu={sum(worker_times):.1f}s")

    changed = compare_results(new_counts, args.disable)

    # Summary recommendation
    new_total = sum(new_counts.values())
    print(f"\n{'='*70}")
    print("RECOMMENDATION:")
    if new_total == EXPECTED_FPF:
        print(f"  FOUND THE BUG: Disabling '{args.disable}' fixes the count!")
        print(f"  Changed partitions: {[list(c[0]) for c in changed]}")
        print(f"  Next step: Fix the '{args.disable}' optimization code.")
    elif new_total == BASELINE_TOTAL:
        print(f"  '{args.disable}' is NOT the culprit. Try the next optimization.")
        if args.disable == 'orbital':
            print(f"  Next: python run_s15_debug.py --disable nonsplit")
        elif args.disable == 'nonsplit':
            print(f"  Next: python run_s15_debug.py --disable fpf_imposs")
        elif args.disable == 'fpf_imposs':
            print(f"  All three suspects eliminated. Bug is elsewhere.")
            print(f"  Check: H^1 cache fingerprint, NonSolvableComplementClassReps, checkpointing")
    else:
        print(f"  Unexpected result. Total changed but doesn't match expected.")
        print(f"  This optimization contributes to the bug but may not be the only issue.")


if __name__ == "__main__":
    main()
