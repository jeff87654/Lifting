###############################################################################
# run_s15.py - Compute S15 conjugacy classes with parallel partition processing
#
# Distributes 41 FPF partitions of 15 across N GAP worker processes.
# Each worker saves subgroup generators to per-partition files.
# After completion, combines inherited S14 classes + FPF classes into
# s15_subgroups.g in the same format as s14_subgroups.g.
#
# Usage:
#   python run_s15.py [--workers N] [--dry-run] [--timeout T]
#   python run_s15.py --combine-only   (skip computation, just combine)
#
###############################################################################

import subprocess
import os
import sys
import time
import re
import ast
import argparse
import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configuration
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
CONJUGACY_CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
N = 15
EXPECTED_TOTAL = 159129  # OEIS A000638(15)
INHERITED_FROM_S14 = 75154  # OEIS A000638(14)
EXPECTED_FPF = EXPECTED_TOTAL - INHERITED_FROM_S14  # 83975

# S13 timing data for cost estimation (seconds) - with latest optimizations
S13_TIMING_OPT = {
    (13,): 0.03, (11,2): 9.6, (10,3): 26, (9,4): 173,
    (9,2,2): 17.8, (8,5): 133, (8,3,2): 90, (7,6): 116,
    (7,4,2): 52, (7,3,3): 23, (7,2,2,2): 1.7, (6,5,2): 88,
    (6,4,3): 181, (6,3,2,2): 74, (5,5,3): 34, (5,4,4): 216,
    (5,4,2,2): 150, (5,3,3,2): 40, (5,2,2,2,2): 4.4,
    (4,4,3,2): 84, (4,3,3,3): 59, (4,3,2,2,2): 100,
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
    # Direct lookup for S13 partitions (won't match for S15 but good baseline)
    if tuple(partition) in S13_TIMING_OPT:
        return S13_TIMING_OPT[tuple(partition)]

    n = sum(partition)
    k = len(partition)
    max_part = max(partition)
    num_2s = sum(1 for p in partition if p == 2)

    # NrTransitiveGroups for each degree
    nr_trans = {1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
                9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104}

    # Product of transitive group counts
    combo_count = 1
    for p in partition:
        combo_count *= nr_trans.get(p, max(1, p))

    # Base cost per combo scales with max(partition)
    base_cost_per_combo = max_part * 0.3

    # C2 optimization discount
    if num_2s >= 2:
        base_cost_per_combo *= 0.3

    cost = combo_count * base_cost_per_combo

    # Scale by degree relative to S13
    degree_scale = (n / 13.0) ** 2.5

    return max(0.1, cost * degree_scale)


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

    print(f"\nPartition assignment ({len(partitions)} partitions -> {num_workers} workers):")
    for i, (parts, load) in enumerate(zip(workers, worker_loads)):
        if not parts:
            continue
        print(f"  Worker {i}: {len(parts)} partitions, est. {load:.0f}s")
        for ps in parts[:5]:
            print(f"    {list(ps)}")
        if len(parts) > 5:
            print(f"    ... and {len(parts)-5} more")

    return workers


def create_worker_gap_script(partitions, worker_id, output_dir):
    """Create a GAP script that processes partitions and saves generators."""
    log_file = os.path.join(output_dir, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(output_dir, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(output_dir, "checkpoints", f"worker_{worker_id}").replace("\\", "/")

    partition_strs = []
    for p in partitions:
        partition_strs.append("[" + ",".join(str(x) for x in p) + "]")
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(partitions)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S14)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Keep database caches (FPF_SUBDIRECT_CACHE, H1_CACHE) warm for speed
# Only clear H1 cache initially to avoid stale entries from previous runs
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
                    pass  # We compute total from partition counts
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


def parse_inherited_subgroups(filepath):
    """Parse s14_subgroups.g into a list of generator lists."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Strip comment lines
    lines = []
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#') or stripped == '':
            continue
        lines.append(line)

    # Join and extract the list between 'return [' and '];'
    text = '\n'.join(lines)

    # Remove 'return' and trailing ';'
    text = text.strip()
    if text.startswith('return'):
        text = text[6:].strip()
    if text.endswith(';'):
        text = text[:-1].strip()

    # Parse as Python list (GAP list syntax is compatible)
    try:
        data = ast.literal_eval(text)
        return data
    except (ValueError, SyntaxError) as e:
        print(f"ERROR parsing {filepath}: {e}")
        # Try chunk-by-chunk parsing as fallback
        return parse_inherited_chunked(text)


def parse_inherited_chunked(text):
    """Fallback parser that reads subgroups one at a time."""
    # The text is like: [ [...], [...], ... ]
    # Remove outer brackets
    text = text.strip()
    if text.startswith('['):
        text = text[1:]
    if text.endswith(']'):
        text = text[:-1]

    subgroups = []
    depth = 0
    current = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '[':
            if depth == 0:
                current = ch
            else:
                current += ch
            depth += 1
        elif ch == ']':
            depth -= 1
            current += ch
            if depth == 0:
                # Parse this subgroup
                try:
                    sg = ast.literal_eval(current.strip())
                    subgroups.append(sg)
                except:
                    pass
                current = ""
        elif depth > 0:
            current += ch
        i += 1

    return subgroups


def join_gap_continuation_lines(filepath):
    """Read a file and join GAP's backslash-continuation lines."""
    with open(filepath, 'r') as f:
        raw_lines = f.readlines()

    # Join lines that end with '\' (GAP's 80-char wrapping)
    joined = []
    current = ""
    for raw_line in raw_lines:
        line = raw_line.rstrip('\n').rstrip('\r')
        if line.endswith('\\'):
            # Continuation: strip the backslash and append next line
            current += line[:-1]
        else:
            current += line
            if current.strip():
                joined.append(current)
            current = ""
    # Don't forget last line if it didn't end with newline
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


def write_subgroups_file(filepath, all_subgroups, n):
    """Write subgroups in the s14_subgroups.g format."""
    now = datetime.datetime.now()
    with open(filepath, 'w') as f:
        f.write(f"# Conjugacy class representatives for S{n}\n")
        f.write(f"# Computed via Holt's algorithm with chief series lifting\n")
        f.write(f"# Computed: {now}\n")
        f.write(f"# Total: {len(all_subgroups)} conjugacy classes\n")
        f.write("return [\n")
        for i, gens in enumerate(all_subgroups):
            # Format generators
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
        f.write("];\n")


def combine_results_into_file(output_dir):
    """Combine inherited S14 classes + FPF partition classes into s15_subgroups.g."""
    s14_file = os.path.join(CONJUGACY_CACHE, "s14_subgroups.g")
    s15_file = os.path.join(CONJUGACY_CACHE, "s15_subgroups.g")
    gens_dir = os.path.join(output_dir, "gens")

    print(f"\nCombining results into {s15_file}...")

    # Step 1: Parse inherited S14 classes
    print(f"  Parsing inherited S14 classes from {s14_file}...")
    inherited = parse_inherited_subgroups(s14_file)
    print(f"  Loaded {len(inherited)} inherited classes")

    if len(inherited) != INHERITED_FROM_S14:
        print(f"  WARNING: Expected {INHERITED_FROM_S14} inherited classes, got {len(inherited)}")

    # Step 2: Extend inherited generators to degree 15 (add fixed point 15)
    print(f"  Extending inherited generators to degree {N}...")
    for sg in inherited:
        for gen in sg:
            gen.append(N)

    # Step 3: Parse FPF partition generators
    print(f"  Parsing FPF partition generators from {gens_dir}...")
    fpf_subgroups = parse_partition_gens(gens_dir)
    print(f"  Loaded {len(fpf_subgroups)} FPF classes")

    # Step 4: Combine
    all_subgroups = inherited + fpf_subgroups
    print(f"  Total: {len(all_subgroups)} classes")

    if len(all_subgroups) != EXPECTED_TOTAL:
        print(f"  WARNING: Expected {EXPECTED_TOTAL}, got {len(all_subgroups)}")

    # Step 5: Write output
    print(f"  Writing {s15_file}...")
    write_subgroups_file(s15_file, all_subgroups, N)
    print(f"  Done! Output: {s15_file}")

    return len(all_subgroups)


def main():
    parser = argparse.ArgumentParser(description='Compute S15 conjugacy classes')
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers')
    parser.add_argument('--dry-run', action='store_true', help='Show assignment without running')
    parser.add_argument('--timeout', type=int, default=21600, help='Per-worker timeout (default 6h)')
    parser.add_argument('--combine-only', action='store_true', help='Skip computation, just combine')
    args = parser.parse_args()

    output_dir = os.path.join(LIFTING_DIR, f"parallel_s{N}")

    print(f"S{N} Conjugacy Class Computation")
    print(f"=" * 60)
    print(f"Expected: {EXPECTED_TOTAL} classes ({INHERITED_FROM_S14} inherited + {EXPECTED_FPF} FPF)")
    print(f"Output:   {os.path.join(CONJUGACY_CACHE, f's{N}_subgroups.g')}")
    print(f"Workers:  {args.workers}")
    print(f"Timeout:  {args.timeout}s per worker")

    if args.combine_only:
        combine_results_into_file(output_dir)
        return

    # Generate FPF partitions
    partitions = partitions_min_part(N)
    print(f"\nFPF partitions of {N}: {len(partitions)}")

    # Assign to workers
    assignments = assign_partitions_to_workers(partitions, args.workers)

    # Filter out empty workers
    active_workers = [(i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active_workers)
    print(f"\nActive workers: {num_active}")

    if args.dry_run:
        print("\n[DRY RUN] Would run with the above assignment.")
        total_est = sum(estimate_partition_cost(p) for p in partitions)
        max_worker_est = max(sum(estimate_partition_cost(p) for p in parts)
                            for _, parts in active_workers)
        print(f"Estimated total CPU: {total_est:.0f}s")
        print(f"Estimated wall-clock: {max_worker_est:.0f}s")
        return

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "gens"), exist_ok=True)
    for worker_id, _ in active_workers:
        os.makedirs(os.path.join(output_dir, "checkpoints", f"worker_{worker_id}"),
                     exist_ok=True)

    # Clear previous result files
    for worker_id, _ in active_workers:
        result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)

    # Create GAP scripts
    scripts = {}
    for worker_id, parts in active_workers:
        script_file = create_worker_gap_script(parts, worker_id, output_dir)
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

        # Collect results as they complete
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

    # Collect and verify results
    print(f"\nCollecting results...")
    total_fpf, partition_counts, worker_times = collect_results(output_dir, args.workers)

    total = INHERITED_FROM_S14 + total_fpf
    print(f"\nResults for S_{N}:")
    print(f"  Inherited from S_{N-1}: {INHERITED_FROM_S14}")
    print(f"  FPF partition classes:  {total_fpf}")
    print(f"  TOTAL:                  {total}")

    if total == EXPECTED_TOTAL:
        print(f"  Status: PASS (matches OEIS A000638 = {EXPECTED_TOTAL})")
    else:
        print(f"  Status: MISMATCH (expected {EXPECTED_TOTAL}, got {total})")
        print(f"  Difference: {total - EXPECTED_TOTAL}")

    if worker_times:
        print(f"\nTiming:")
        print(f"  Wall-clock:       {overall_elapsed:.1f}s ({overall_elapsed/3600:.2f}h)")
        print(f"  Max worker CPU:   {max(worker_times):.1f}s ({max(worker_times)/3600:.2f}h)")
        print(f"  Sum worker CPU:   {sum(worker_times):.1f}s ({sum(worker_times)/3600:.2f}h)")
        print(f"  Speedup:          {sum(worker_times)/overall_elapsed:.1f}x")

    # Print per-partition breakdown
    if partition_counts:
        print(f"\nPer-partition counts ({len(partition_counts)} partitions):")
        for part_str in sorted(partition_counts.keys()):
            print(f"  {part_str}: {partition_counts[part_str]}")

    # Combine into final output file if count matches
    if total == EXPECTED_TOTAL:
        combine_results_into_file(output_dir)
    else:
        print(f"\nSkipping file generation due to count mismatch.")
        print(f"Run with --combine-only after resolving issues.")


if __name__ == "__main__":
    main()
