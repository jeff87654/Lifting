#!/usr/bin/env python3
"""
run_dedup_s17.py - Deduplicate S17 FPF groups up to partition-normalizer conjugacy.

Reads generator files from parallel_s17/gens/, distributes partitions across 6 GAP
workers using LPT scheduling, and runs invariant-based dedup + pairwise
RepresentativeAction within each partition.

Usage: python run_dedup_s17.py
"""

import subprocess
import os
import glob
import re
import time
import sys

# Flush prints immediately (important when running in background)
sys.stdout.reconfigure(line_buffering=True)

BASE = r"C:\Users\jeffr\Downloads\Lifting"
GENS_DIR = os.path.join(BASE, "parallel_s17", "gens")
DEDUP_DIR = os.path.join(BASE, "parallel_s17", "dedup")
NUM_WORKERS = 6

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

INHERITED_S16 = 686165  # S1-S16 total conjugacy classes
OEIS_S17 = 1466358      # OEIS A000638 value for S17

os.makedirs(DEDUP_DIR, exist_ok=True)


def count_entries(filepath):
    """Count groups in a gens file, handling backslash continuations."""
    count = 0
    buf = ''
    with open(filepath) as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.endswith('\\'):
                buf += line[:-1]
            else:
                buf += line
                if buf.strip():
                    count += 1
                buf = ''
    return count


def partition_from_filename(filename):
    """Extract partition list from filename like gens_8_4_3_2.txt -> [8,4,3,2]."""
    name = os.path.basename(filename)
    parts_str = name.replace('gens_', '').replace('.txt', '').split('_')
    return [int(p) for p in parts_str]


def lpt_schedule(items, num_workers):
    """LPT (Longest Processing Time) scheduling.
    items: list of (partition, count, filepath)
    Returns: list of num_workers lists, each containing assigned items.
    """
    items_sorted = sorted(items, key=lambda x: -x[1])
    workers = [[] for _ in range(num_workers)]
    loads = [0] * num_workers
    for item in items_sorted:
        min_idx = loads.index(min(loads))
        workers[min_idx].append(item)
        loads[min_idx] += item[1]
    return workers, loads


def generate_worker_script(worker_id, assignments):
    """Generate a GAP script for one dedup worker."""
    log_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s17/dedup/dedup_s17_w{worker_id}.log"
    script_path = os.path.join(DEDUP_DIR, f"dedup_s17_w{worker_id}.g")

    lines = []
    lines.append(f'# Dedup worker {worker_id} for S17 - auto-generated')
    lines.append(f'LogTo("{log_file}");')
    lines.append(f'Print("Worker {worker_id} loading code...\\n");')
    lines.append(f'Read("C:/Users/jeffr/Downloads/Lifting/parallel_s17/dedup/dedup_loader.g");')
    lines.append(f'Read("C:/Users/jeffr/Downloads/Lifting/parallel_s17/dedup/dedup_common.g");')
    lines.append(f'Print("Worker {worker_id} starting, {len(assignments)} partitions\\n");')
    lines.append('')

    for partition, expected_count, gens_file in assignments:
        part_gap = "[" + ",".join(map(str, partition)) + "]"
        gens_path = gens_file.replace("\\", "/")
        lines.append(f'DedupPartition({part_gap}, "{gens_path}");')

    lines.append('')
    lines.append(f'Print("\\nWorker {worker_id} finished at ", StringTime(Runtime()), "\\n");')
    lines.append('LogTo();')
    lines.append('QUIT;')

    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return script_path


def launch_gap_worker(worker_id, script_path):
    """Launch a GAP process for one worker."""
    script_cygwin = script_path.replace("\\", "/").replace("C:/", "/cygdrive/c/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cygwin}"'
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, cwd=GAP_RUNTIME
    )
    return process


def parse_results(log_file):
    """Parse RESULT lines from a worker log file.
    Returns dict: partition_str -> (input_count, unique_count, time_ms)
    """
    results = {}
    if not os.path.exists(log_file):
        return results
    with open(log_file, encoding='utf-8', errors='replace') as f:
        for line in f:
            # Match: RESULT [ 8, 4, 3, 2 ] INPUT 116100 UNIQUE 116100 TIME 12345
            m = re.match(
                r'RESULT\s+\[\s*([\d,\s]+)\s*\]\s+INPUT\s+(\d+)\s+UNIQUE\s+(\d+)\s+TIME\s+(\d+)',
                line.strip()
            )
            if m:
                parts = [int(x.strip()) for x in m.group(1).split(',')]
                part_key = tuple(parts)
                results[part_key] = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return results


def main():
    print("=" * 70)
    print("S17 FPF Dedup - Partition-normalizer conjugacy deduplication")
    print("=" * 70)

    # Step 1: Scan gens files
    print("\nScanning gens files...")
    partitions = []
    for f in sorted(glob.glob(os.path.join(GENS_DIR, "gens_*.txt"))):
        if f.endswith('.bak'):
            continue
        count = count_entries(f)
        partition = partition_from_filename(f)
        partitions.append((partition, count, os.path.abspath(f)))

    total_input = sum(c for _, c, _ in partitions)
    print(f"Found {len(partitions)} partitions, {total_input:,} total groups")

    # Step 2: LPT schedule
    workers, loads = lpt_schedule(partitions, NUM_WORKERS)

    print(f"\nWorker allocation ({NUM_WORKERS} workers):")
    print(f"{'Worker':<8} {'Groups':>8} {'Parts':>6}  Largest partition")
    print("-" * 65)
    for w in range(NUM_WORKERS):
        if workers[w]:
            largest = max(workers[w], key=lambda x: x[1])
            lpart = "_".join(map(str, largest[0]))
            print(f"  W{w+1:<5} {loads[w]:>8,} {len(workers[w]):>6}  [{lpart}]={largest[1]:,}")
    spread = max(loads) - min(loads)
    print(f"  Load spread: {spread:,} groups")

    # Step 3: Generate GAP scripts
    print("\nGenerating GAP worker scripts...")
    script_paths = []
    for w in range(NUM_WORKERS):
        path = generate_worker_script(w + 1, workers[w])
        script_paths.append(path)
        print(f"  W{w+1}: {os.path.basename(path)} ({len(workers[w])} partitions)")

    # Step 4: Launch workers with staggered starts (avoid Cygwin file-lock deadlock)
    STAGGER_DELAY = 15  # seconds between launches
    print(f"\nLaunching {NUM_WORKERS} GAP workers (staggered by {STAGGER_DELAY}s)...")
    start_time = time.time()
    processes = []
    for w in range(NUM_WORKERS):
        proc = launch_gap_worker(w + 1, script_paths[w])
        processes.append(proc)
        print(f"  W{w+1}: PID {proc.pid}")
        if w < NUM_WORKERS - 1:
            time.sleep(STAGGER_DELAY)

    # Step 5: Wait for all workers (no timeout - large partitions may take hours)
    print("\nWaiting for workers to complete...")
    print("(Monitor progress via: tail -f parallel_s17/dedup/dedup_s17_wN.log)")
    completed = [False] * NUM_WORKERS
    while not all(completed):
        for w in range(NUM_WORKERS):
            if not completed[w]:
                try:
                    proc = processes[w]
                    proc.wait(timeout=30)
                    completed[w] = True
                    elapsed = time.time() - start_time
                    rc = proc.returncode
                    print(f"  W{w+1}: finished (rc={rc}, {elapsed:.0f}s elapsed)")
                except subprocess.TimeoutExpired:
                    pass
        if not all(completed):
            elapsed = time.time() - start_time
            running = [f"W{w+1}" for w in range(NUM_WORKERS) if not completed[w]]
            print(f"  [{elapsed:.0f}s] Still running: {', '.join(running)}")

    total_time = time.time() - start_time
    print(f"\nAll workers finished in {total_time:.0f}s ({total_time/3600:.1f}h)")

    # Step 6: Parse results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    all_results = {}
    for w in range(NUM_WORKERS):
        log_file = os.path.join(DEDUP_DIR, f"dedup_s17_w{w+1}.log")
        results = parse_results(log_file)
        all_results.update(results)
        if not results:
            print(f"  WARNING: No results from W{w+1} ({log_file})")

    # Print per-partition results sorted by partition
    print(f"\n{'Partition':<30} {'Input':>8} {'Unique':>8} {'Dups':>6} {'Time':>8}")
    print("-" * 70)

    total_unique = 0
    total_dups = 0
    missing = []

    for partition, count, filepath in sorted(partitions, key=lambda x: x[0]):
        part_key = tuple(partition)
        part_str = "[" + ",".join(map(str, partition)) + "]"
        if part_key in all_results:
            inp, uniq, tms = all_results[part_key]
            dups = inp - uniq
            total_unique += uniq
            total_dups += dups
            time_str = f"{tms/1000:.0f}s" if tms < 600000 else f"{tms/60000:.1f}m"
            print(f"  {part_str:<28} {inp:>8,} {uniq:>8,} {dups:>6,} {time_str:>8}")
        else:
            missing.append(part_str)
            print(f"  {part_str:<28} {count:>8,}     MISSING")

    print("-" * 70)
    print(f"  {'TOTAL FPF':<28} {total_input:>8,} {total_unique:>8,} {total_dups:>6,}")
    print(f"  {'+ Inherited (S1-S16)':<28} {'':>8} {INHERITED_S16:>8,}")
    print(f"  {'= TOTAL S17':<28} {'':>8} {total_unique + INHERITED_S16:>8,}")
    print(f"  {'Expected (OEIS A000638)':<28} {'':>8} {OEIS_S17:>8,}")

    expected_fpf = OEIS_S17 - INHERITED_S16
    if total_unique == expected_fpf:
        print(f"\n  MATCH! FPF count {total_unique:,} = {expected_fpf:,} (expected)")
    elif missing:
        print(f"\n  WARNING: {len(missing)} partitions missing results: {', '.join(missing)}")
        print(f"  FPF so far: {total_unique:,}, expected: {expected_fpf:,}, "
              f"gap: {expected_fpf - total_unique:,}")
    else:
        diff = total_unique - expected_fpf
        print(f"\n  MISMATCH! FPF count {total_unique:,} vs expected {expected_fpf:,} "
              f"(diff={diff:+,})")

    # Save summary
    summary_path = os.path.join(DEDUP_DIR, "dedup_summary.txt")
    with open(summary_path, "w") as f:
        f.write(f"S17 FPF Dedup Summary\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total time: {total_time:.0f}s\n")
        f.write(f"Input groups: {total_input}\n")
        f.write(f"Unique groups: {total_unique}\n")
        f.write(f"Duplicates removed: {total_dups}\n")
        f.write(f"Inherited (S1-S16): {INHERITED_S16}\n")
        f.write(f"Total S17: {total_unique + INHERITED_S16}\n")
        f.write(f"Expected (OEIS): {OEIS_S17}\n")
        f.write(f"\nPer-partition:\n")
        for partition, count, filepath in sorted(partitions, key=lambda x: x[0]):
            part_key = tuple(partition)
            part_str = "[" + ",".join(map(str, partition)) + "]"
            if part_key in all_results:
                inp, uniq, tms = all_results[part_key]
                f.write(f"  {part_str}: input={inp}, unique={uniq}, time={tms}ms\n")
            else:
                f.write(f"  {part_str}: MISSING (input file had {count})\n")
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
