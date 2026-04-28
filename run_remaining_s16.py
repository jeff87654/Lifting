###############################################################################
# run_remaining_s16.py - Launch 6 remaining S16 partitions with TI invariant
#
# Partitions: [8,8], [8,4,4], [4,4,4,4], [4,4,4,2,2], [4,4,2,2,2,2], [4,2,2,2,2,2,2]
#
# Each runs in its own GAP process, resuming from latest checkpoint.
###############################################################################

import subprocess
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")

# Worker ID range for new workers (avoid collision with existing)
WORKER_BASE = 90

# Partitions to compute (fresh, no checkpoints)
PARTITIONS = [
    {"partition": [8, 8]},
    {"partition": [8, 4, 4]},
    {"partition": [4, 4, 4, 4]},
    {"partition": [4, 4, 4, 2, 2]},
    {"partition": [4, 4, 2, 2, 2, 2]},
    {"partition": [4, 2, 2, 2, 2, 2, 2]},
]


def create_worker_script(partition_info, worker_id):
    """Create a GAP script for a single partition (fresh, no checkpoint)."""
    part = partition_info["partition"]

    part_str = "_".join(str(x) for x in part)
    part_gap = "[" + ",".join(str(x) for x in part) + "]"

    log_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{worker_id}.log"
    result_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{worker_id}_results.txt"
    heartbeat_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{worker_id}_heartbeat.txt"
    ckpt_dir = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{worker_id}"
    gen_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_{part_str}.txt"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting FRESH at ", StringTime(Runtime()), "\\n");
Print("Partition: {part_gap}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S15)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Enable heartbeat
_HEARTBEAT_FILE := "{heartbeat_file}";

# Clear H1 cache
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

PrintTo("{heartbeat_file}", "starting partition {part_gap}\\n");

partStart := Runtime();
fpf_classes := FindFPFClassesForPartition(16, {part_gap});
partTime := (Runtime() - partStart) / 1000.0;

Print("\\n========================================\\n");
Print("Partition {part_gap}: ", Length(fpf_classes), " classes (", partTime, "s)\\n");

# Save generators
PrintTo("{gen_file}", "");
for _h_idx in [1..Length(fpf_classes)] do
    AppendTo("{gen_file}",
        "# Group ", _h_idx, "\\n",
        GeneratorsOfGroup(fpf_classes[_h_idx]), "\\n");
od;

# Write result
AppendTo("{result_file}",
    "{part_gap}: ", String(Length(fpf_classes)),
    " classes (", String(Int(partTime*1000)), "ms)\\n");

Print("\\nWorker {worker_id} finished at ", StringTime(Runtime()), "\\n");
PrintTo("{heartbeat_file}", "DONE: {part_gap} = ", String(Length(fpf_classes)), " classes\\n");
LogTo();
QUIT;
'''

    script_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)

    # Ensure checkpoint dir exists
    os.makedirs(os.path.join(LIFTING_DIR, "parallel_s16", "checkpoints", f"worker_{worker_id}"), exist_ok=True)
    os.makedirs(os.path.join(LIFTING_DIR, "parallel_s16", "gens"), exist_ok=True)

    # Clear previous result file if any
    result_path = os.path.join(LIFTING_DIR, "parallel_s16", f"worker_{worker_id}_results.txt")
    if os.path.exists(result_path):
        os.remove(result_path)

    return script_file


def run_gap_worker(script_file, worker_id, timeout=86400):
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


def main():
    print(f"S16 Remaining Partitions - Resuming with TI Invariant")
    print(f"=" * 60)
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Create worker scripts
    workers = []
    for i, pinfo in enumerate(PARTITIONS):
        wid = WORKER_BASE + i
        script = create_worker_script(pinfo, wid)
        workers.append((wid, pinfo["partition"], script))
        print(f"  Worker {wid}: {pinfo['partition']} (fresh, no checkpoint)")

    print(f"\nLaunching {len(workers)} workers...")
    overall_start = time.time()

    # Launch all workers in parallel
    futures = {}
    with ProcessPoolExecutor(max_workers=len(workers)) as executor:
        for wid, part, script in workers:
            future = executor.submit(run_gap_worker, script, wid)
            futures[future] = (wid, part)

        # Collect results as they complete
        for future in as_completed(futures):
            wid, part = futures[future]
            result = future.result()
            elapsed = result['elapsed']
            rc = result['returncode']

            # Read result file
            result_file = os.path.join(LIFTING_DIR, "parallel_s16", f"worker_{wid}_results.txt")
            result_text = ""
            if os.path.exists(result_file):
                with open(result_file) as f:
                    result_text = f.read().strip()

            if rc == 0:
                print(f"\n  Worker {wid} ({part}) completed in {elapsed:.0f}s")
                if result_text:
                    print(f"    Result: {result_text}")
            else:
                print(f"\n  Worker {wid} ({part}) FAILED (rc={rc}) after {elapsed:.0f}s")
                if result['stderr']:
                    print(f"    stderr: {result['stderr'][:300]}")

    overall_elapsed = time.time() - overall_start
    print(f"\n{'=' * 60}")
    print(f"All workers finished in {overall_elapsed:.0f}s ({overall_elapsed/3600:.1f}h)")
    print(f"Ended: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Summarize results
    print(f"\n{'=' * 60}")
    print("Results:")
    for wid, part, _ in workers:
        result_file = os.path.join(LIFTING_DIR, "parallel_s16", f"worker_{wid}_results.txt")
        if os.path.exists(result_file):
            with open(result_file) as f:
                print(f"  {f.read().strip()}")
        else:
            print(f"  Worker {wid} ({part}): NO RESULT FILE")


if __name__ == "__main__":
    main()
