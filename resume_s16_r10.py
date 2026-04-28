"""
S16 Round 10: Relaunch CCS workers with improved invariant dedup.

Fix: _DeduplicateCCSbyConjugacy now uses ComputeSubgroupInvariant (with
ConjugacyClasses + 2-subset orbits) for large inputs (>5000 FPF reps).
Also uses cached invariant keys for H^g lookup (conjugation preserves all
group-theoretic invariants). This reduces bucket sizes from ~1000+ to ~5-20,
giving ~100x speedup on the RA calls.

Workers:
  W63: [4,4,4,2,2] (resume from 16 combos) + [4,2,2,2,2,2,2]
  W64: [4,4,2,2,2,2] (resume from 6 combos) + [3,3,3,3,2,2]
  W65: [6,4,2,2,2] (resume from 61 combos)
"""

import subprocess
import os
import sys
import time
import shutil

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
CKPT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

def launch_worker(wid, gap_code, desc):
    """Write GAP script and launch worker."""
    script_file = os.path.join(LIFTING_DIR, f"temp_worker_{wid}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)

    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_worker_{wid}.g"
    log_file = os.path.join(OUTPUT_DIR, f"worker_{wid}.log")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    proc = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
         f'./gap.exe -q "{script_path}" 2>&1'],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        env=env,
        cwd=gap_runtime
    )
    print(f"  Launched W{wid}: {desc} (PID {proc.pid})")
    return proc

def make_partition_code(wid, partitions, results_file, heartbeat_file):
    """Generate GAP code for processing multiple partitions with checkpoint resume."""
    ckpt_dir = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
    results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{results_file}"
    hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{heartbeat_file}"

    code = f'''
LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (round 10 - rich invariant dedup) starting at ", Runtime()/1000, "s\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{hb_path}";
CHECKPOINT_DIR := "{ckpt_dir}";
'''
    for i, part in enumerate(partitions):
        part_str = ",".join(str(x) for x in part)
        code += f'''
Print("\\n========================================\\n");
Print("Partition [{part_str}]\\n");
Print("========================================\\n");
PrintTo("{hb_path}", "starting partition [{part_str}]\\n");

t0 := Runtime();
result_{i} := FindFPFClassesForPartition(16, [{part_str}]);
elapsed_{i} := Runtime() - t0;
Print("[{part_str}]: ", Length(result_{i}), " classes (", elapsed_{i}, "ms)\\n");
AppendTo("{results_path}", "[{part_str}]: ", Length(result_{i}), " classes (", elapsed_{i}, "ms)\\n");
PrintTo("{hb_path}", "completed [{part_str}] ", Length(result_{i}), " classes\\n");

# Clear caches between partitions
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
GASMAN("collect");
'''

    code += f'''
PrintTo("{hb_path}", "ALL DONE\\n");
Print("\\nWorker {wid} ALL DONE\\n");
LogTo();
QUIT;
'''
    return code

print(f"\n=== S16 Round 10: Launching 3 workers at {time.strftime('%H:%M:%S')} ===\n")

# Set up checkpoint directories
# W63: [4,4,4,2,2] - copy from worker_59 (which was copied from worker_53)
# W64: [4,4,2,2,2,2] - copy from worker_60 (which was copied from worker_54)
# W65: [6,4,2,2,2] - copy from worker_61 (which was copied from worker_55, updated to 61 combos)
for wid, src in [(63, "worker_59"), (64, "worker_60"), (65, "worker_61")]:
    ckpt_dst = os.path.join(CKPT_DIR, f"worker_{wid}")
    os.makedirs(ckpt_dst, exist_ok=True)
    src_dir = os.path.join(CKPT_DIR, src)
    if os.path.exists(src_dir):
        for f in os.listdir(src_dir):
            src_file = os.path.join(src_dir, f)
            dst_file = os.path.join(ckpt_dst, f)
            if not os.path.exists(dst_file) or os.path.getmtime(src_file) > os.path.getmtime(dst_file):
                shutil.copy2(src_file, dst_file)
                print(f"  Copied {src}/{f} -> worker_{wid}/ ({os.path.getsize(src_file)} bytes)")

# Worker 63: [4,4,4,2,2] (resume from 16 combos) + [4,2,2,2,2,2,2]
code_63 = make_partition_code(63,
    [[4,4,4,2,2], [4,2,2,2,2,2,2]],
    f"worker_63_results.txt",
    f"worker_63_heartbeat.txt")
p63 = launch_worker(63, code_63, "[4,4,4,2,2] + [4,2,2,2,2,2,2]")

# Worker 64: [4,4,2,2,2,2] (resume from 6 combos) + [3,3,3,3,2,2]
code_64 = make_partition_code(64,
    [[4,4,2,2,2,2], [3,3,3,3,2,2]],
    f"worker_64_results.txt",
    f"worker_64_heartbeat.txt")
p64 = launch_worker(64, code_64, "[4,4,2,2,2,2] + [3,3,3,3,2,2]")

# Worker 65: [6,4,2,2,2] (resume from 61 combos)
code_65 = make_partition_code(65,
    [[6,4,2,2,2]],
    f"worker_65_results.txt",
    f"worker_65_heartbeat.txt")
p65 = launch_worker(65, code_65, "[6,4,2,2,2]")

print(f"\nAll 3 R10 workers launched.")
print(f"Still running: W43 (PID 63860, [8,8]), W47 (PID 55688, [8,4,4]),")
print(f"  W58 (PID 59416, C2^8 BFS), W62 (PID 73716, [4,4,4,4] C2^8 AllSubgroups)")
print(f"\nMonitor: python monitor_s16.py --once")
