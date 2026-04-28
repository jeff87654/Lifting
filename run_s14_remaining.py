###############################################################################
# run_s14_remaining.py - Process remaining S14 partitions after first run
#
# First run completed 13/34 partitions. This processes the remaining 21.
# Also includes results from first run for final summation.
###############################################################################

import subprocess
import os
import sys
import time
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

# Results from first run (verified)
FIRST_RUN_RESULTS = {
    (14,): 63, (10,4): 801, (9,5): 274, (8,3,3): 1080,
    (7,7): 50, (7,4,3): 262, (6,6,2): 2059, (6,5,3): 723,
    (6,3,3,2): 1026, (5,5,4): 400, (5,3,3,3): 145,
    (10,2,2): 359, (3,3,3,3,2): 127,
}

# Remaining partitions to compute
REMAINING = [
    (12,2), (11,3), (9,3,2), (8,6), (8,4,2), (8,2,2,2),
    (7,5,2), (7,3,2,2), (6,4,4), (6,4,2,2), (6,2,2,2,2),
    (5,5,2,2), (5,4,3,2), (5,3,2,2,2), (4,4,4,2), (4,4,3,3),
    (4,4,2,2,2), (4,3,3,2,2), (4,2,2,2,2,2), (3,3,2,2,2,2),
    (2,2,2,2,2,2,2),
]

# Cost estimates (from S13 scaling)
COST_ESTIMATES = {
    (12,2): 2000, (11,3): 600, (9,3,2): 400, (8,6): 3000,
    (8,4,2): 1500, (8,2,2,2): 200, (7,5,2): 500, (7,3,2,2): 200,
    (6,4,4): 2000, (6,4,2,2): 800, (6,2,2,2,2): 100,
    (5,5,2,2): 300, (5,4,3,2): 800, (5,3,2,2,2): 200,
    (4,4,4,2): 600, (4,4,3,3): 600, (4,4,2,2,2): 300,
    (4,3,3,2,2): 400, (4,2,2,2,2,2): 50, (3,3,2,2,2,2): 50,
    (2,2,2,2,2,2,2): 20,
}


def assign_lpt(partitions, num_workers):
    """LPT scheduling."""
    costs = [(COST_ESTIMATES.get(p, 100), p) for p in partitions]
    costs.sort(reverse=True)

    workers = [[] for _ in range(num_workers)]
    loads = [0.0] * num_workers

    for cost, part in costs:
        min_idx = loads.index(min(loads))
        workers[min_idx].append(part)
        loads[min_idx] += cost

    for i, (parts, load) in enumerate(zip(workers, loads)):
        print(f"  Worker {i}: {len(parts)} partitions, est. {load:.0f}s")
        for p in parts:
            print(f"    {list(p)}")

    return workers


def create_gap_script(n, partitions, worker_id, output_dir):
    """Create GAP script for a worker."""
    log_file = os.path.join(output_dir, f"w{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"w{worker_id}_results.txt").replace("\\", "/")

    part_strs = ["[" + ",".join(str(x) for x in p) + "]" for p in partitions]
    partitions_gap = "[" + ",\n    ".join(part_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting\\n");
Print("Processing {len(partitions)} partitions for S_{n}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

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
    fpf_classes := FindFPFClassesForPartition({n}, part);
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
    script_file = os.path.join(output_dir, f"w{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)
    return script_file


def run_gap_worker(script_file, worker_id, timeout=14400):
    """Run a single GAP worker."""
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
    ]

    start = time.time()
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=env, cwd=GAP_RUNTIME)
        stdout, stderr = process.communicate(timeout=timeout)
        return {'worker_id': worker_id, 'returncode': process.returncode,
                'elapsed': time.time() - start, 'stderr': stderr}
    except subprocess.TimeoutExpired:
        process.kill()
        return {'worker_id': worker_id, 'returncode': -1,
                'elapsed': timeout, 'stderr': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'worker_id': worker_id, 'returncode': -2,
                'elapsed': time.time() - start, 'stderr': str(e)}


def main():
    n = 14
    num_workers = 8

    print(f"S14 Remaining Partitions ({len(REMAINING)} of 34)")
    print("=" * 50)
    print(f"Already completed: {len(FIRST_RUN_RESULTS)} partitions")
    print(f"  Sum of first run: {sum(FIRST_RUN_RESULTS.values())}")

    # Assign remaining partitions
    print(f"\nAssigning {len(REMAINING)} partitions to {num_workers} workers:")
    assignments = assign_lpt(REMAINING, num_workers)

    active = [(i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active)

    # Create output directory
    output_dir = os.path.join(LIFTING_DIR, "parallel_s14_r2")
    os.makedirs(output_dir, exist_ok=True)

    # Clear previous results
    for wid, _ in active:
        rf = os.path.join(output_dir, f"w{wid}_results.txt")
        if os.path.exists(rf):
            os.remove(rf)

    # Create scripts
    scripts = {}
    for wid, parts in active:
        scripts[wid] = create_gap_script(n, parts, wid, output_dir)

    print(f"\nLaunching {num_active} workers...")
    overall_start = time.time()

    futures = {}
    with ProcessPoolExecutor(max_workers=num_active) as executor:
        for wid, _ in active:
            future = executor.submit(run_gap_worker, scripts[wid], wid)
            futures[future] = wid

        for future in as_completed(futures):
            wid = futures[future]
            result = future.result()
            if result['returncode'] == 0:
                print(f"  Worker {wid} completed in {result['elapsed']:.1f}s")
            else:
                print(f"  Worker {wid} FAILED (rc={result['returncode']}) after {result['elapsed']:.1f}s")
                if result['stderr']:
                    print(f"    stderr: {result['stderr'][:300]}")

    overall_elapsed = time.time() - overall_start
    print(f"\nAll workers finished in {overall_elapsed:.1f}s wall-clock")

    # Collect second run results
    new_counts = {}
    for wid in range(num_workers):
        rf = os.path.join(output_dir, f"w{wid}_results.txt")
        if not os.path.exists(rf):
            continue
        with open(rf) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOTAL") or line.startswith("TIME") or not line:
                    continue
                parts = line.rsplit(' ', 1)
                if len(parts) == 2:
                    new_counts[parts[0].strip()] = int(parts[1])

    # Combine with first run
    total_fpf = sum(FIRST_RUN_RESULTS.values()) + sum(new_counts.values())
    inherited = 20832  # S_13
    total = inherited + total_fpf

    print(f"\n{'='*50}")
    print(f"Results for S_14:")
    print(f"  Inherited from S_13:    {inherited}")
    print(f"  First run FPF classes:  {sum(FIRST_RUN_RESULTS.values())}")
    print(f"  Second run FPF classes: {sum(new_counts.values())}")
    print(f"  Total FPF classes:      {total_fpf}")
    print(f"  TOTAL:                  {total}")

    expected = 75154
    if total == expected:
        print(f"  Status: PASS (matches OEIS A000638 = {expected})")
    else:
        print(f"  Status: FAIL (expected {expected}, got {total})")
        print(f"  Difference: {total - expected}")

    # Per-partition breakdown
    print(f"\nPer-partition counts:")
    all_counts = {}
    for p, c in FIRST_RUN_RESULTS.items():
        all_counts[str(list(p))] = c
    for ps, c in new_counts.items():
        all_counts[ps] = c
    for ps in sorted(all_counts.keys()):
        print(f"  {ps}: {all_counts[ps]}")

    print(f"\nPartitions completed: {len(all_counts)} / 34")
    if len(all_counts) < 34:
        print("  MISSING partitions!")


if __name__ == "__main__":
    main()
