"""
Resume S16 computation after all workers died.

Status:
  - 14 partitions completed (52,652 FPF classes + 7 from skipped combos)
  - 5 partitions have checkpoints (can resume)
  - 36 partitions need fresh start
  - Total: 41 partitions to process across 8 workers

Uses the updated code with:
  - SafeNaturalHomByNSG (coset action fallback)
  - Combo-level CALL_WITH_CATCH (skips broken combos gracefully)
"""

import subprocess
import os
import sys
import json
import time
import math
from pathlib import Path

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16
NUM_WORKERS = 8
WORKER_ID_START = 20  # Use IDs 20-27 to avoid conflict with old workers

# NrTransitiveGroups for degrees 1..16
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954
}

# Completed partitions (from worker result files)
COMPLETED = {
    (14, 2), (13, 3), (12, 4), (12, 2, 2), (10, 6), (10, 4, 2),
    (10, 3, 3), (9, 7), (9, 5, 2), (9, 4, 3), (8, 5, 3),
    (7, 6, 3), (6, 6, 4), (6, 5, 3, 2)
}

# Partitions with checkpoints (worker_id -> partition)
HAS_CHECKPOINT = {
    1: (8, 8),
    3: (8, 6, 2),
    4: (8, 4, 4),
    5: (5, 4, 4, 3),
    7: (6, 4, 4, 2),
}


def get_all_fpf_partitions(n):
    """Generate all partitions of n with min part >= 2."""
    result = []
    def _gen(remaining, max_part, current):
        if remaining == 0:
            result.append(tuple(current))
            return
        for p in range(min(max_part, remaining), 1, -1):
            _gen(remaining - p, p, current + [p])
    _gen(n, n, [])
    return result


def estimate_cost(partition):
    """Estimate relative cost of a partition."""
    # Number of combos = product of NrTransitiveGroups for each part,
    # divided by k! for groups of k repeated parts
    from collections import Counter
    counts = Counter(partition)

    combos = 1
    for part, k in counts.items():
        nr = NR_TRANSITIVE.get(part, 1)
        # Multiset coefficient: C(nr + k - 1, k)
        c = 1
        for i in range(k):
            c = c * (nr + i) // (i + 1)
        combos *= c

    # Scale by average per-combo cost (larger parts = more expensive)
    max_part = max(partition)
    if max_part >= 12:
        per_combo = 5.0
    elif max_part >= 8:
        per_combo = 2.0
    elif max_part >= 6:
        per_combo = 1.0
    else:
        per_combo = 0.3

    # Single-part partitions are near-instant
    if len(partition) == 1:
        return 0.1

    return combos * per_combo


def assign_to_workers(partitions, num_workers):
    """LPT scheduling: assign partitions to workers by estimated cost."""
    costs = [(p, estimate_cost(p)) for p in partitions]
    costs.sort(key=lambda x: -x[1])  # Most expensive first

    workers = [[] for _ in range(num_workers)]
    worker_loads = [0.0] * num_workers

    for p, cost in costs:
        # Assign to least-loaded worker
        min_idx = worker_loads.index(min(worker_loads))
        workers[min_idx].append(p)
        worker_loads[min_idx] += cost

    return workers, worker_loads


def create_worker_gap_script(partitions, worker_id, checkpoint_info=None):
    """Create GAP script for a worker. checkpoint_info maps partition -> old checkpoint dir."""
    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(OUTPUT_DIR, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    heartbeat_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")

    partition_strs = ["[" + ",".join(str(x) for x in p) + "]" for p in partitions]
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    # Checkpoint files are already copied by Python (shutil.copy2) before launching GAP.
    # No GAP-side copy needed.
    ckpt_copy_lines = ""

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(partitions)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Copy checkpoint files from old workers if available
{ckpt_copy_lines}

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\n========================================\\n");
    Print("Partition ", part, ":\\n");
    partStart := Runtime();

    PrintTo("{heartbeat_file}", "starting partition ", part, "\\n");

    fpf_classes := FindFPFClassesForPartition({N}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    partStr := JoinStringsWithSeparator(List(part, String), "_");
    genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
    PrintTo(genFile, "");
    for _h_idx in [1..Length(fpf_classes)] do
        _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                      g -> ListPerm(g, {N}));
        AppendTo(genFile, String(_gens), "\\n");
    od;
    Print("  Generators saved to ", genFile, "\\n");

    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");

    if IsBound(GasmanStatistics) then
        Print("  Memory: ", GasmanStatistics(), "\\n");
    fi;

    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    PrintTo("{heartbeat_file}",
        "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {worker_id} complete: ", totalCount, " total classes in ",
      workerTime, "s\\n");

AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

if IsBound(SaveFPFSubdirectCache) then
    SaveFPFSubdirectCache();
fi;

LogTo();
QUIT;
'''

    script_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)
    return script_file


def launch_gap_worker(script_file, worker_id):
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


def main():
    all_fpf = get_all_fpf_partitions(N)
    print(f"Total FPF partitions of {N}: {len(all_fpf)}")

    remaining = [p for p in all_fpf if p not in COMPLETED]
    print(f"Completed: {len(COMPLETED)}, Remaining: {len(remaining)}")

    # Build checkpoint info: map partition -> old checkpoint dir
    checkpoint_info = {}
    for old_wid, part in HAS_CHECKPOINT.items():
        old_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{old_wid}")
        ckpt_file = os.path.join(old_dir, f"ckpt_{N}_{'_'.join(str(x) for x in part)}.g")
        if os.path.exists(ckpt_file):
            checkpoint_info[part] = old_dir.replace("\\", "/")
            print(f"  Checkpoint available for {list(part)} (from W{old_wid})")

    # LPT scheduling
    assignments, loads = assign_to_workers(remaining, NUM_WORKERS)

    print(f"\n=== Worker Assignments ===")
    for i in range(NUM_WORKERS):
        wid = WORKER_ID_START + i
        parts = assignments[i]
        has_ckpt = [p for p in parts if p in checkpoint_info]
        print(f"  W{wid}: {len(parts)} partitions, est_cost={loads[i]:.0f}"
              f"{' (checkpoints: ' + str([list(p) for p in has_ckpt]) + ')' if has_ckpt else ''}")
        for p in parts:
            ckpt_marker = " [CHECKPOINT]" if p in checkpoint_info else ""
            print(f"    {list(p)} (cost={estimate_cost(p):.0f}){ckpt_marker}")

    if "--dry-run" in sys.argv:
        return 0

    # Create checkpoint directories and launch workers
    processes = {}
    for i in range(NUM_WORKERS):
        wid = WORKER_ID_START + i
        parts = assignments[i]
        if not parts:
            continue

        ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}")
        os.makedirs(ckpt_dir, exist_ok=True)

        # Copy checkpoint files from old workers
        for part in parts:
            if part in checkpoint_info:
                old_dir = checkpoint_info[part]
                part_str = "_".join(str(x) for x in part)
                old_file = os.path.join(old_dir.replace("/", os.sep), f"ckpt_{N}_{part_str}.g")
                new_file = os.path.join(ckpt_dir, f"ckpt_{N}_{part_str}.g")
                if os.path.exists(old_file) and not os.path.exists(new_file):
                    import shutil
                    shutil.copy2(old_file, new_file)
                    print(f"  Copied checkpoint {old_file} -> {new_file}")

        # Build per-worker checkpoint info
        worker_ckpt = {p: checkpoint_info[p] for p in parts if p in checkpoint_info}

        script = create_worker_gap_script(parts, wid, worker_ckpt if worker_ckpt else None)
        proc = launch_gap_worker(script, wid)
        processes[wid] = proc
        print(f"Launched W{wid} (PID {proc.pid}): {len(parts)} partitions")

    # Monitor for 60s
    print(f"\nMonitoring for 60s...")
    for tick in range(12):
        time.sleep(5)
        line = f"  [{(tick+1)*5}s]"
        for wid in sorted(processes.keys()):
            proc = processes[wid]
            rc = proc.poll()
            if rc is not None:
                line += f" W{wid}:EXIT({rc})"
                continue
            hb_path = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
            if os.path.exists(hb_path):
                with open(hb_path) as f:
                    hb = f.read().strip()
                # Shorten heartbeat
                hb_short = hb[:50]
                line += f" W{wid}:{hb_short}"
            else:
                line += f" W{wid}:loading"
        print(line)

    print(f"\nAll workers launched. Use monitor_s16.py to track progress.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
