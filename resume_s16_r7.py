"""
S16 Round 7: Resume 7 remaining partitions with GF(2) orbit dedup fix.

Distribution (5 workers):
  W52: [4,4,4,4]        (35 remaining of 70 combos, C_2^8 combos) - ckpt from worker_45
  W53: [4,4,4,2,2]      (20 remaining of 35 combos, C_2^8) + [4,2,2,2,2,2,2] (5 combos)
  W54: [4,4,2,2,2,2]    (10 remaining of 15 combos, C_2^8) + [3,3,3,3,2,2] (5 combos)
  W55: [6,4,2,2,2]      (57 remaining of 80 combos) - ckpt from worker_24
  W56: [5,5,2,2,2]      (15 combos, fresh)

W43 (PID 63860) still running [8,8]
W47 (PID 55688) still running [8,4,4]
"""

import subprocess
import os
import sys
import time
import shutil

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
PARALLEL_DIR = os.path.join(BASE_DIR, "parallel_s16")
GENS_DIR = os.path.join(PARALLEL_DIR, "gens")
CKPT_DIR = os.path.join(PARALLEL_DIR, "checkpoints")

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

# Worker assignments: worker_id -> list of (partition, source_checkpoint_worker_or_None)
ASSIGNMENTS = {
    52: [([4,4,4,4], "worker_45")],
    53: [([4,4,4,2,2], "worker_46"), ([4,2,2,2,2,2,2], None)],
    54: [([4,4,2,2,2,2], "worker_44"), ([3,3,3,3,2,2], None)],
    55: [([6,4,2,2,2], "worker_24")],
    56: [([5,5,2,2,2], None)],
}


def partition_to_str(p):
    return "_".join(str(x) for x in p)


def partition_to_gap(p):
    return "[" + ",".join(str(x) for x in p) + "]"


def ckpt_filename(partition):
    return f"ckpt_16_{partition_to_str(partition)}.g"


def setup_checkpoints():
    """Copy checkpoint files from old workers to new worker checkpoint dirs."""
    for wid, assignments in ASSIGNMENTS.items():
        worker_ckpt_dir = os.path.join(CKPT_DIR, f"worker_{wid}")
        os.makedirs(worker_ckpt_dir, exist_ok=True)

        for partition, source_worker in assignments:
            if source_worker is not None:
                src_file = os.path.join(CKPT_DIR, source_worker, ckpt_filename(partition))
                dst_file = os.path.join(worker_ckpt_dir, ckpt_filename(partition))
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dst_file)
                    print(f"  Copied {source_worker}/{ckpt_filename(partition)} -> worker_{wid}/ ({os.path.getsize(src_file)} bytes)")
                else:
                    print(f"  WARNING: {src_file} not found!")


def create_gap_script(wid, assignments):
    """Generate GAP script for a worker."""
    log_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log"
    ckpt_dir = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
    gens_dir = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens"
    heartbeat_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_heartbeat.txt"
    results_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_results.txt"

    script = f'''LogTo("{log_file}");
Print("Worker {wid} (round 7 - GF2 orbit dedup) starting at ", Runtime()/1000, "s\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";
'''

    for partition, _ in assignments:
        gap_part = partition_to_gap(partition)
        gens_file = f"{gens_dir}/gens_{partition_to_str(partition)}.txt"

        script += f'''
Print("\\n========================================\\n");
Print("Partition {gap_part}\\n");
Print("========================================\\n");
t0 := Runtime();

PrintTo("{heartbeat_file}", "starting partition {gap_part}\\n");

result_{partition_to_str(partition)} := FindFPFClassesForPartition(16, {gap_part});
t_elapsed := Runtime() - t0;
Print("Partition {gap_part}: ", Length(result_{partition_to_str(partition)}),
      " FPF classes (", t_elapsed, "ms)\\n");

# Save generators
output := OutputTextFile("{gens_file}", false);
for H in result_{partition_to_str(partition)} do
    PrintTo(output, GeneratorsOfGroup(H), "\\n");
od;
CloseStream(output);
Print("Saved generators to {gens_file}\\n");

# Append to results file
AppendTo("{results_file}",
    "{gap_part}: ", Length(result_{partition_to_str(partition)}),
    " classes (", t_elapsed, "ms)\\n");

PrintTo("{heartbeat_file}", "completed {gap_part} ", Length(result_{partition_to_str(partition)}), " classes ", t_elapsed, "ms\\n");

# Clear caches between partitions
Unbind(result_{partition_to_str(partition)});
GASMAN("collect");
Print("Memory after GC: ", GasmanStatistics(), "\\n");
'''

    script += f'''
Print("\\nWorker {wid} ALL DONE at ", Runtime()/1000, "s\\n");
PrintTo("{heartbeat_file}", "ALL DONE\\n");
LogTo();
QUIT;
'''
    return script


def launch_worker(wid):
    """Launch a single GAP worker."""
    script_file = os.path.join(PARALLEL_DIR, f"worker_{wid}_script.g")
    script_content = create_gap_script(wid, ASSIGNMENTS[wid])

    with open(script_file, "w") as f:
        f.write(script_content)

    script_path_cygwin = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_script.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    process = subprocess.Popen(
        [BASH_EXE, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path_cygwin}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME
    )
    return process


def main():
    if "--dry-run" in sys.argv:
        print("=== DRY RUN: Worker assignments ===")
        for wid, assignments in sorted(ASSIGNMENTS.items()):
            parts = [partition_to_gap(p) for p, _ in assignments]
            ckpts = [f"ckpt from {src}" if src else "fresh" for _, src in assignments]
            print(f"  W{wid}: {', '.join(f'{p} ({c})' for p, c in zip(parts, ckpts))}")
        return

    print(f"=== S16 Round 7: Launching 5 workers at {time.strftime('%H:%M:%S')} ===")
    print()

    # Step 1: Setup checkpoints
    print("Setting up checkpoints...")
    setup_checkpoints()
    print()

    # Step 2: Launch workers
    processes = {}
    for wid in sorted(ASSIGNMENTS.keys()):
        parts = [partition_to_gap(p) for p, _ in ASSIGNMENTS[wid]]
        print(f"Launching W{wid}: {', '.join(parts)}")
        proc = launch_worker(wid)
        processes[wid] = proc
        print(f"  PID: {proc.pid}")

    print(f"\nAll 5 workers launched. Monitoring...")
    print(f"Also running: W43 (PID 63860, [8,8]), W47 (PID 55688, [8,4,4])")
    print()

    # Step 3: Monitor
    start_time = time.time()
    completed = set()

    while len(completed) < len(processes):
        time.sleep(60)
        elapsed = time.time() - start_time
        print(f"\n[{time.strftime('%H:%M:%S')}] +{int(elapsed)}s")

        for wid, proc in sorted(processes.items()):
            if wid in completed:
                continue
            ret = proc.poll()
            if ret is not None:
                completed.add(wid)
                print(f"  W{wid}: FINISHED (exit={ret})")
                # Print results
                results_file = os.path.join(PARALLEL_DIR, f"worker_{wid}_results.txt")
                if os.path.exists(results_file):
                    with open(results_file) as f:
                        print(f"    {f.read().strip()}")
            else:
                # Check heartbeat
                hb_file = os.path.join(PARALLEL_DIR, f"worker_{wid}_heartbeat.txt")
                if os.path.exists(hb_file):
                    with open(hb_file) as f:
                        hb = f.read().strip()
                    print(f"  W{wid}: {hb}")
                else:
                    print(f"  W{wid}: running (no heartbeat yet)")

    print(f"\n=== All R7 workers finished at {time.strftime('%H:%M:%S')} ===")
    print(f"Total wall time: {int(time.time() - start_time)}s")

    # Print summary
    print("\n=== Results ===")
    for wid in sorted(ASSIGNMENTS.keys()):
        results_file = os.path.join(PARALLEL_DIR, f"worker_{wid}_results.txt")
        if os.path.exists(results_file):
            with open(results_file) as f:
                for line in f:
                    print(f"  W{wid}: {line.strip()}")


if __name__ == "__main__":
    main()
