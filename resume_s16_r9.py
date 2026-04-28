"""
S16 Round 9: Relaunch stuck workers with CCS fast path fix.

Killed workers:
  W53 (PID 47356) - [4,4,4,2,2] stuck on combo #17 (|P|=512, exponential lifting)
  W54 (PID 44512) - [4,4,2,2,2,2] stuck on combo #7 (|P|=512, exponential lifting)
  W55 (PID 61680) - [6,4,2,2,2] stuck on combo #52 (|P|=3072, exponential lifting)
  W57 (PID 53756) - [4,4,4,4] in AllSubgroups for C_2^8 combo

Fix: Added CCS (ConjugacyClassesSubgroups) fast path in lifting_algorithm.g for
non-abelian groups with |P| <= 4096 and numLayers >= 8. This replaces exponential
layer-by-layer lifting with direct subgroup class enumeration.

Workers:
  W59: [4,4,4,2,2] (resume from W53 checkpoint) + [4,2,2,2,2,2,2]
  W60: [4,4,2,2,2,2] (resume from W54 checkpoint) + [3,3,3,3,2,2]
  W61: [6,4,2,2,2] (resume from W55 checkpoint)
  W62: [4,4,4,4] (resume from W57 checkpoint)
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

def make_partition_code(wid, partitions, checkpoint_sources, results_file, heartbeat_file):
    """Generate GAP code for processing multiple partitions with checkpoint resume."""
    ckpt_dir_cyg = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
    results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{results_file}"
    hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{heartbeat_file}"

    code = f'''
LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (round 9 - CCS fast path) starting at ", Runtime()/1000, "s\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{hb_path}";
CHECKPOINT_DIR := "{ckpt_dir_cyg}";
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

print(f"\n=== S16 Round 9: Launching 4 workers at {time.strftime('%H:%M:%S')} ===\n")

# Set up checkpoint directories
for wid, src in [(59, "worker_53"), (60, "worker_54"), (61, "worker_55"), (62, "worker_57")]:
    ckpt_dst = os.path.join(CKPT_DIR, f"worker_{wid}")
    os.makedirs(ckpt_dst, exist_ok=True)
    src_dir = os.path.join(CKPT_DIR, src)
    if os.path.exists(src_dir):
        for f in os.listdir(src_dir):
            src_file = os.path.join(src_dir, f)
            dst_file = os.path.join(ckpt_dst, f)
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                print(f"  Copied {src}/{f} -> worker_{wid}/ ({os.path.getsize(src_file)} bytes)")

# Worker 59: [4,4,4,2,2] (resume from W53) + [4,2,2,2,2,2,2]
code_59 = make_partition_code(59,
    [[4,4,4,2,2], [4,2,2,2,2,2,2]],
    ["worker_53"],
    f"worker_59_results.txt",
    f"worker_59_heartbeat.txt")
p59 = launch_worker(59, code_59, "[4,4,4,2,2] + [4,2,2,2,2,2,2]")

# Worker 60: [4,4,2,2,2,2] (resume from W54) + [3,3,3,3,2,2]
code_60 = make_partition_code(60,
    [[4,4,2,2,2,2], [3,3,3,3,2,2]],
    ["worker_54"],
    f"worker_60_results.txt",
    f"worker_60_heartbeat.txt")
p60 = launch_worker(60, code_60, "[4,4,2,2,2,2] + [3,3,3,3,2,2]")

# Worker 61: [6,4,2,2,2] (resume from W55)
code_61 = make_partition_code(61,
    [[6,4,2,2,2]],
    ["worker_55"],
    f"worker_61_results.txt",
    f"worker_61_heartbeat.txt")
p61 = launch_worker(61, code_61, "[6,4,2,2,2]")

# Worker 62: [4,4,4,4] (resume from W57)
code_62 = make_partition_code(62,
    [[4,4,4,4]],
    ["worker_57"],
    f"worker_62_results.txt",
    f"worker_62_heartbeat.txt")
p62 = launch_worker(62, code_62, "[4,4,4,4]")

print(f"\nAll 4 R9 workers launched.")
print(f"Still running: W43 (PID 63860, [8,8]), W47 (PID 55688, [8,4,4]), W58 (PID 59416, C2^8 combos)")
print(f"\nMonitor: python monitor_s16.py --once")
