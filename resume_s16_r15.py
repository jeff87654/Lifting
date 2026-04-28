"""
S16 Round 15: Relaunch W77/W78/W79 replacements.

W77 (PID 76516), W78 (PID 22380), W79 (PID 80656) all died around 10:12-10:16
due to memory pressure from the BFS test. No new checkpoint progress was saved.

Relaunch with existing checkpoints:
  W83: [4,4,4,2,2] (resume from 16 combos/8805 groups)
  W84: [4,4,2,2,2,2] (resume from 6 combos/2154 groups)
  W85: [6,4,2,2,2] (resume from 62 combos/17857 groups)
"""

import subprocess
import os
import time
import shutil

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
CKPT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

def launch_worker(wid, gap_code, desc, mem="8g"):
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
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o {mem} "{script_path}" 2>&1'],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        env=env,
        cwd=gap_runtime
    )
    print(f"  Launched W{wid}: {desc} (PID {proc.pid}, {mem} mem)")
    return proc

def make_partition_code(wid, partitions, results_file, heartbeat_file):
    ckpt_dir = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
    results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{results_file}"
    hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{heartbeat_file}"

    code = f'''LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (round 15 - relaunch) starting at ", Runtime()/1000, "s\\n");
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

print(f"\n=== S16 Round 15: Relaunch 3 dead workers at {time.strftime('%H:%M:%S')} ===\n")

# Copy checkpoints from dead workers
checkpoint_sources = {
    83: ("worker_77", "ckpt_16_4_4_4_2_2.g"),    # 16 combos
    84: ("worker_78", "ckpt_16_4_4_2_2_2_2.g"),  # 6 combos
    85: ("worker_79", "ckpt_16_6_4_2_2_2.g"),    # 62 combos
}

for wid, (src_worker, ckpt_file) in checkpoint_sources.items():
    ckpt_dst = os.path.join(CKPT_DIR, f"worker_{wid}")
    os.makedirs(ckpt_dst, exist_ok=True)
    src_file = os.path.join(CKPT_DIR, src_worker, ckpt_file)
    dst_file = os.path.join(ckpt_dst, ckpt_file)
    if os.path.exists(src_file):
        shutil.copy2(src_file, dst_file)
        sz = os.path.getsize(src_file)
        print(f"  Copied {src_worker}/{ckpt_file} -> worker_{wid}/ ({sz:,} bytes)")
    else:
        print(f"  WARNING: {src_file} not found!")

# Worker 83: [4,4,4,2,2] (resume from 16/35 combos)
code_83 = make_partition_code(83,
    [[4,4,4,2,2]],
    "worker_83_results.txt",
    "worker_83_heartbeat.txt")
p83 = launch_worker(83, code_83, "[4,4,4,2,2] (16/35)", mem="8g")

# Worker 84: [4,4,2,2,2,2] (resume from 6/15 combos)
code_84 = make_partition_code(84,
    [[4,4,2,2,2,2]],
    "worker_84_results.txt",
    "worker_84_heartbeat.txt")
p84 = launch_worker(84, code_84, "[4,4,2,2,2,2] (6/15)", mem="8g")

# Worker 85: [6,4,2,2,2] (resume from 62/80 combos)
code_85 = make_partition_code(85,
    [[6,4,2,2,2]],
    "worker_85_results.txt",
    "worker_85_heartbeat.txt")
p85 = launch_worker(85, code_85, "[6,4,2,2,2] (62/80)", mem="6g")

print(f"\nAll 3 R15 workers launched at {time.strftime('%H:%M:%S')}.")
