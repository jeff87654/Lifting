#!/usr/bin/env python3
"""
run_dedup_s17_v2.py - Improved S17 FPF dedup orchestrator.

Key improvements over run_dedup_s17.py:
  - One partition per GAP process (prevents memory accumulation)
  - At most 4 concurrent GAP processes (reduced from 6)
  - Skips already-completed partitions (checks for RESULT in log files)
  - Invariant checkpointing: if a process dies in Phase 3, Phases 1+2
    work is preserved in bucket files and reloaded on retry
  - Per-partition log files
  - Status monitoring every 60 seconds
  - LPT scheduling (biggest partitions first)

Usage: python run_dedup_s17_v2.py
"""

import subprocess
import os
import glob
import re
import time
import sys

# Flush prints immediately
sys.stdout.reconfigure(line_buffering=True)

BASE = r"C:\Users\jeffr\Downloads\Lifting"
GENS_DIR = os.path.join(BASE, "parallel_s17", "gens")
DEDUP_DIR = os.path.join(BASE, "parallel_s17", "dedup")
SCRIPT_DIR = os.path.join(DEDUP_DIR, "dedup_s17")
LOG_DIR = os.path.join(DEDUP_DIR, "dedup_s17")
INV_DIR = os.path.join(DEDUP_DIR, "inv")
MAX_CONCURRENT = 6
STAGGER_DELAY = 10  # seconds between launches (avoid Cygwin file-lock races)

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

INHERITED_S16 = 686165   # S1-S16 total conjugacy classes
OEIS_S17 = 1466358       # OEIS A000638 value for S17

# Partitions already completed in the first run (0 duplicates found for all)
COMPLETED_PARTITIONS = {
    (4, 4, 4, 3, 2),
    (6, 4, 4, 3),
    (6, 4, 3, 2, 2),
    (4, 4, 3, 2, 2, 2),
    (8, 6, 3),
    (5, 4, 4, 2, 2),
}

# Pre-known results for completed partitions (input, unique, time_ms)
COMPLETED_RESULTS = {
    (4, 4, 4, 3, 2):    (106779, 106779, 6445328),
    (6, 4, 4, 3):       (74919,  74919,  11096813),
    (6, 4, 3, 2, 2):    (59732,  59732,  5887234),
    (4, 4, 3, 2, 2, 2): (55009,  55009,  2236390),
    (8, 6, 3):          (37985,  37985,  5277109),
    (5, 4, 4, 2, 2):    (28310,  28310,  3886609),
}

os.makedirs(SCRIPT_DIR, exist_ok=True)
os.makedirs(INV_DIR, exist_ok=True)


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


def partition_suffix(partition):
    """[8,4,3,2] -> '8_4_3_2'"""
    return "_".join(map(str, partition))


def log_file_for_partition(partition):
    """Return log file path for a partition."""
    return os.path.join(LOG_DIR, f"log_{partition_suffix(partition)}.log")


def script_file_for_partition(partition):
    """Return GAP script file path for a partition."""
    return os.path.join(SCRIPT_DIR, f"run_{partition_suffix(partition)}.g")


def check_completed_in_log(partition):
    """Check if a partition already has a RESULT line in its log file."""
    log_path = log_file_for_partition(partition)
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = re.match(
                    r'RESULT\s+\[\s*([\d,\s]+)\s*\]\s+INPUT\s+(\d+)\s+UNIQUE\s+(\d+)\s+TIME\s+(\d+)',
                    line.strip()
                )
                if m:
                    parts = [int(x.strip()) for x in m.group(1).split(',')]
                    if parts == partition:
                        return (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    except Exception:
        pass
    return None


def get_last_log_line(partition):
    """Get the last non-empty line from a partition's log file."""
    log_path = log_file_for_partition(partition)
    if not os.path.exists(log_path):
        return "(no log yet)"
    try:
        last_line = ""
        with open(log_path, encoding='utf-8', errors='replace') as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        return last_line[-120:] if len(last_line) > 120 else last_line
    except Exception:
        return "(read error)"


def generate_gap_script(partition, gens_file):
    """Generate a GAP script for one partition's dedup."""
    part_gap = "[" + ",".join(map(str, partition)) + "]"
    gens_path = gens_file.replace("\\", "/")
    log_path = log_file_for_partition(partition).replace("\\", "/")
    script_path = script_file_for_partition(partition)

    lines = [
        f'# Dedup for partition {part_gap} - auto-generated',
        f'LogTo("{log_path}");',
        f'Print("Dedup {part_gap} starting\\n");',
        f'Read("C:/Users/jeffr/Downloads/Lifting/parallel_s17/dedup/dedup_loader.g");',
        f'Read("C:/Users/jeffr/Downloads/Lifting/parallel_s17/dedup/dedup_common_v2.g");',
        f'DedupPartition({part_gap}, "{gens_path}");',
        f'Print("Dedup {part_gap} finished\\n");',
        f'LogTo();',
        f'QUIT;',
    ]

    with open(script_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return script_path


def launch_gap(script_path):
    """Launch a GAP process for one partition."""
    script_cygwin = script_path.replace("\\", "/").replace("C:/", "/cygdrive/c/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
        f'./gap.exe -q -o 0 "{script_cygwin}"'
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, cwd=GAP_RUNTIME
    )
    return process


def parse_result_from_log(partition):
    """Parse the RESULT line from a partition's log file."""
    log_path = log_file_for_partition(partition)
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = re.match(
                    r'RESULT\s+\[\s*([\d,\s]+)\s*\]\s+INPUT\s+(\d+)\s+UNIQUE\s+(\d+)\s+TIME\s+(\d+)',
                    line.strip()
                )
                if m:
                    parts = [int(x.strip()) for x in m.group(1).split(',')]
                    if parts == partition:
                        return (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    except Exception:
        pass
    return None


def main():
    print("=" * 70)
    print("S17 FPF Dedup v2 - One partition per process, checkpointed")
    print("=" * 70)

    # Step 1: Scan gens files
    print("\nScanning gens files...")
    all_partitions = []
    for f in sorted(glob.glob(os.path.join(GENS_DIR, "gens_*.txt"))):
        if f.endswith('.bak'):
            continue
        count = count_entries(f)
        partition = partition_from_filename(f)
        all_partitions.append((partition, count, os.path.abspath(f)))

    total_input = sum(c for _, c, _ in all_partitions)
    print(f"Found {len(all_partitions)} partitions, {total_input:,} total groups")

    # Step 2: Identify remaining partitions
    already_done = {}
    remaining = []

    for partition, count, filepath in all_partitions:
        part_key = tuple(partition)

        # Check hardcoded completed list
        if part_key in COMPLETED_PARTITIONS:
            already_done[part_key] = COMPLETED_RESULTS.get(
                part_key, (count, count, 0)
            )
            continue

        # Check if log file already has a RESULT
        result = check_completed_in_log(partition)
        if result is not None:
            already_done[part_key] = result
            continue

        remaining.append((partition, count, filepath))

    print(f"\nAlready completed: {len(already_done)} partitions")
    print(f"Remaining: {len(remaining)} partitions, "
          f"{sum(c for _, c, _ in remaining):,} groups")

    if not remaining:
        print("\nAll partitions already completed!")
        _print_final_summary(all_partitions, already_done)
        return

    # Step 3: Sort remaining by count descending (LPT - biggest first)
    remaining.sort(key=lambda x: -x[1])

    print(f"\nRemaining partitions (sorted by size, biggest first):")
    for partition, count, _ in remaining[:10]:
        psuffix = partition_suffix(partition)
        bucket_exists = os.path.exists(
            os.path.join(INV_DIR, f"buckets_{psuffix}.txt")
        )
        resume_tag = " [has buckets, will resume at Phase 3]" if bucket_exists else ""
        print(f"  [{psuffix.replace('_', ',')}]: {count:,} groups{resume_tag}")
    if len(remaining) > 10:
        print(f"  ... and {len(remaining) - 10} more")

    # Step 4: Generate GAP scripts for all remaining partitions
    print(f"\nGenerating GAP scripts...")
    scripts = {}
    for partition, count, filepath in remaining:
        script = generate_gap_script(partition, filepath)
        scripts[tuple(partition)] = script

    # Step 5: Process queue with limited concurrency
    print(f"\nLaunching up to {MAX_CONCURRENT} concurrent GAP processes...")
    print(f"Stagger delay: {STAGGER_DELAY}s between launches")
    print()

    start_time = time.time()
    queue = list(remaining)  # Copy the remaining list as our work queue
    active = {}  # part_key -> (process, partition, launch_time)
    finished_count = 0
    total_count = len(remaining)

    def try_launch_next():
        """Launch the next partition from the queue if slots are available."""
        nonlocal queue
        if not queue or len(active) >= MAX_CONCURRENT:
            return False

        partition, count, filepath = queue.pop(0)
        part_key = tuple(partition)
        psuffix = partition_suffix(partition)
        script = scripts[part_key]

        proc = launch_gap(script)
        active[part_key] = (proc, partition, time.time())
        elapsed = time.time() - start_time
        print(f"  [{elapsed:6.0f}s] LAUNCHED [{psuffix.replace('_', ',')}] "
              f"({count:,} groups), PID {proc.pid}, "
              f"{len(active)}/{MAX_CONCURRENT} slots")
        return True

    # Initial launches with stagger
    for _ in range(min(MAX_CONCURRENT, len(queue))):
        try_launch_next()
        if queue and len(active) < MAX_CONCURRENT:
            time.sleep(STAGGER_DELAY)

    # Monitor loop
    last_status = time.time()
    while active or queue:
        # Check for completed processes
        completed_keys = []
        for part_key, (proc, partition, launch_time) in active.items():
            rc = proc.poll()
            if rc is not None:
                completed_keys.append(part_key)
                finished_count += 1
                elapsed = time.time() - start_time
                proc_time = time.time() - launch_time
                psuffix = partition_suffix(partition)

                # Check result
                result = parse_result_from_log(partition)
                if result is not None:
                    inp, uniq, tms = result
                    dups = inp - uniq
                    already_done[part_key] = result
                    print(f"  [{elapsed:6.0f}s] DONE [{psuffix.replace('_', ',')}] "
                          f"rc={rc}, {proc_time:.0f}s wall, "
                          f"input={inp}, unique={uniq}, dups={dups}, "
                          f"({finished_count}/{total_count})")
                else:
                    print(f"  [{elapsed:6.0f}s] DONE [{psuffix.replace('_', ',')}] "
                          f"rc={rc}, {proc_time:.0f}s wall, "
                          f"NO RESULT (may have crashed), "
                          f"({finished_count}/{total_count})")

        # Remove completed from active
        for key in completed_keys:
            del active[key]

        # Launch new processes from queue
        if completed_keys:
            for _ in range(min(len(queue), MAX_CONCURRENT - len(active))):
                launched = try_launch_next()
                if launched and queue and len(active) < MAX_CONCURRENT:
                    time.sleep(STAGGER_DELAY)

        # Status update every 60 seconds
        now = time.time()
        if now - last_status >= 60 and active:
            last_status = now
            elapsed = now - start_time
            print(f"\n  --- Status at {elapsed:.0f}s ({elapsed/3600:.1f}h) ---")
            print(f"  Queue: {len(queue)} | Active: {len(active)} | "
                  f"Done: {finished_count}/{total_count}")
            for part_key, (proc, partition, launch_time) in active.items():
                psuffix = partition_suffix(partition)
                proc_time = now - launch_time
                last_line = get_last_log_line(partition)
                print(f"    [{psuffix.replace('_', ',')}] "
                      f"{proc_time:.0f}s: {last_line}")
            print()

        # Brief sleep to avoid busy-waiting
        if active:
            time.sleep(5)

    total_time = time.time() - start_time
    print(f"\nAll {total_count} partitions finished in {total_time:.0f}s "
          f"({total_time/3600:.1f}h)")

    # Step 6: Final summary
    _print_final_summary(all_partitions, already_done)


def _print_final_summary(all_partitions, all_results):
    """Print and save the final summary of all partitions."""
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n{'Partition':<30} {'Input':>8} {'Unique':>8} {'Dups':>6} {'Time':>10}")
    print("-" * 72)

    total_input = 0
    total_unique = 0
    total_dups = 0
    missing = []

    for partition, count, filepath in sorted(all_partitions, key=lambda x: x[0]):
        part_key = tuple(partition)
        part_str = "[" + ",".join(map(str, partition)) + "]"
        total_input += count

        if part_key in all_results:
            inp, uniq, tms = all_results[part_key]
            dups = inp - uniq
            total_unique += uniq
            total_dups += dups
            if tms < 600000:
                time_str = f"{tms/1000:.0f}s"
            elif tms < 36000000:
                time_str = f"{tms/60000:.1f}m"
            else:
                time_str = f"{tms/3600000:.1f}h"
            print(f"  {part_str:<28} {inp:>8,} {uniq:>8,} {dups:>6,} {time_str:>10}")
        else:
            missing.append((part_str, count))
            print(f"  {part_str:<28} {count:>8,}     MISSING")

    print("-" * 72)
    print(f"  {'TOTAL FPF':<28} {total_input:>8,} {total_unique:>8,} "
          f"{total_dups:>6,}")
    print(f"  {'+ Inherited (S1-S16)':<28} {'':>8} {INHERITED_S16:>8,}")
    print(f"  {'= TOTAL S17':<28} {'':>8} "
          f"{total_unique + INHERITED_S16:>8,}")
    print(f"  {'Expected (OEIS A000638)':<28} {'':>8} {OEIS_S17:>8,}")

    expected_fpf = OEIS_S17 - INHERITED_S16
    if total_unique == expected_fpf and not missing:
        print(f"\n  MATCH! FPF count {total_unique:,} = {expected_fpf:,} (expected)")
    elif missing:
        missing_input = sum(c for _, c in missing)
        print(f"\n  WARNING: {len(missing)} partitions missing results "
              f"({missing_input:,} input groups)")
        for pstr, c in missing[:10]:
            print(f"    {pstr}: {c:,} groups")
        if len(missing) > 10:
            print(f"    ... and {len(missing) - 10} more")
        print(f"  FPF so far: {total_unique:,}, expected: {expected_fpf:,}, "
              f"gap: {expected_fpf - total_unique:,}")
    else:
        diff = total_unique - expected_fpf
        print(f"\n  MISMATCH! FPF count {total_unique:,} vs expected "
              f"{expected_fpf:,} (diff={diff:+,})")

    # Save summary
    summary_path = os.path.join(DEDUP_DIR, "dedup_summary_v2.txt")
    with open(summary_path, "w") as f:
        f.write(f"S17 FPF Dedup Summary (v2)\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input groups: {total_input}\n")
        f.write(f"Unique groups: {total_unique}\n")
        f.write(f"Duplicates removed: {total_dups}\n")
        f.write(f"Inherited (S1-S16): {INHERITED_S16}\n")
        f.write(f"Total S17: {total_unique + INHERITED_S16}\n")
        f.write(f"Expected (OEIS): {OEIS_S17}\n")
        f.write(f"\nPer-partition:\n")
        for partition, count, filepath in sorted(all_partitions, key=lambda x: x[0]):
            part_key = tuple(partition)
            part_str = "[" + ",".join(map(str, partition)) + "]"
            if part_key in all_results:
                inp, uniq, tms = all_results[part_key]
                f.write(f"  {part_str}: input={inp}, unique={uniq}, "
                        f"time={tms}ms\n")
            else:
                f.write(f"  {part_str}: MISSING (input file had {count})\n")
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
