"""
S16 Round 12: Relaunch W68 for [4,4,4,4] + [4,2,2,2,2,2,2] with fixed BFS code.

Fixes in this round:
  - String keys instead of integer keys in rrefToKey (avoids big-integer slowdown)
  - Memory fix: free allSubs before BFS, free fpfRREFs during BFS
  - GC after RREF cleanup
"""

import subprocess
import os
import shutil
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
CKPT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

wid = 72  # New worker ID to avoid conflicts

# Set up checkpoint from worker_52 (35 combos, 7792 groups for [4,4,4,4])
ckpt_dst = os.path.join(CKPT_DIR, f"worker_{wid}")
os.makedirs(ckpt_dst, exist_ok=True)
src_file = os.path.join(CKPT_DIR, "worker_52", "ckpt_16_4_4_4_4.g")
dst_file = os.path.join(ckpt_dst, "ckpt_16_4_4_4_4.g")
shutil.copy2(src_file, dst_file)
sz = os.path.getsize(src_file)
print(f"Copied checkpoint: {sz:,} bytes")

# Verify checkpoint
with open(dst_file, 'r') as f:
    first_lines = [f.readline() for _ in range(3)]
    print(f"Checkpoint header: {first_lines[1].strip()}")

ckpt_dir_gap = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_results.txt"
hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_heartbeat.txt"

gap_code = f'''
LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (round 12 - BFS string key fix) starting at ", Runtime()/1000, "s\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{hb_path}";
CHECKPOINT_DIR := "{ckpt_dir_gap}";

Print("\\n========================================\\n");
Print("Partition [4,4,4,4]\\n");
Print("========================================\\n");
PrintTo("{hb_path}", "starting partition [4,4,4,4]\\n");

t0 := Runtime();
result_0 := FindFPFClassesForPartition(16, [4,4,4,4]);
elapsed_0 := Runtime() - t0;
Print("[4,4,4,4]: ", Length(result_0), " classes (", elapsed_0, "ms)\\n");
AppendTo("{results_path}", "[4,4,4,4]: ", Length(result_0), " classes (", elapsed_0, "ms)\\n");
PrintTo("{hb_path}", "completed [4,4,4,4] ", Length(result_0), " classes\\n");

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
GASMAN("collect");

Print("\\n========================================\\n");
Print("Partition [4,2,2,2,2,2,2]\\n");
Print("========================================\\n");
PrintTo("{hb_path}", "starting partition [4,2,2,2,2,2,2]\\n");

t0 := Runtime();
result_1 := FindFPFClassesForPartition(16, [4,2,2,2,2,2,2]);
elapsed_1 := Runtime() - t0;
Print("[4,2,2,2,2,2,2]: ", Length(result_1), " classes (", elapsed_1, "ms)\\n");
AppendTo("{results_path}", "[4,2,2,2,2,2,2]: ", Length(result_1), " classes (", elapsed_1, "ms)\\n");
PrintTo("{hb_path}", "completed [4,2,2,2,2,2,2] ", Length(result_1), " classes\\n");

PrintTo("{hb_path}", "ALL DONE\\n");
Print("\\nWorker {wid} ALL DONE\\n");
LogTo();
QUIT;
'''

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
     f'./gap.exe -q -o 12g "{script_path}" 2>&1'],
    stdout=open(log_file, "w"),
    stderr=subprocess.STDOUT,
    env=env,
    cwd=gap_runtime
)
print(f"\nLaunched W{wid}: [4,4,4,4] + [4,2,2,2,2,2,2] (PID {proc.pid})")
print(f"Monitor: tail -f parallel_s16/worker_{wid}.log")
