"""
S16 Round 14: Restart [4,4,4,4] with optimized integer BFS + launch 2 remaining partitions.

1. BFS optimization verified: [2,2,2,2,2,2]=36, [4,4,4]=894, S2-S10=1593 ALL PASS.
   New BFS: 928 FPF -> 12 classes in 31ms (was hours with old code).
   For [4,4,4,4] all-V4 combo (C2^8, 191K FPF), expect ~2-10s BFS vs 6+h old code.

2. W76 killed (old BFS code, stuck for 7h on all-V4 combo).

Workers:
  W80: [4,4,4,4] (resume from 35 combos checkpoint) - NEW optimized BFS code
  W81: [4,2,2,2,2,2,2] (fresh, small partition)
  W82: [3,3,3,3,2,2] (fresh)

Still running:
  W43 (PID 63860): [8,8] - 974/1275 combos, stuck on |P|=2.58M combo
  W47 (PID 55688): [8,4,4] - 689/750 combos, actively progressing
  W77 (PID 76516): [4,4,4,2,2] - heavy lifting layer
  W78 (PID 22380): [4,4,2,2,2,2] - heavy lifting layer
  W79 (PID 80656): [6,4,2,2,2] - combo #62, progressing
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

def launch_worker(wid, gap_code, desc, mem="8g"):
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
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o {mem} "{script_path}" 2>&1'],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        env=env,
        cwd=gap_runtime
    )
    print(f"  Launched W{wid}: {desc} (PID {proc.pid}, {mem} mem)")
    return proc

def make_partition_code(wid, partitions, results_file, heartbeat_file):
    """Generate GAP code for processing multiple partitions with checkpoint resume."""
    ckpt_dir = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_{wid}"
    results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{results_file}"
    hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/{heartbeat_file}"

    code = f'''LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (round 14 - optimized integer BFS) starting at ", Runtime()/1000, "s\\n");
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

print(f"\n=== S16 Round 14: Launching 3 workers at {time.strftime('%H:%M:%S')} ===\n")

# Set up checkpoint directories
# W80: [4,4,4,4] - copy checkpoint from W76 (which was copied from W52, 35 combos)
ckpt_w80 = os.path.join(CKPT_DIR, "worker_80")
os.makedirs(ckpt_w80, exist_ok=True)
src_ckpt = os.path.join(CKPT_DIR, "worker_76", "ckpt_16_4_4_4_4.g")
dst_ckpt = os.path.join(ckpt_w80, "ckpt_16_4_4_4_4.g")
if os.path.exists(src_ckpt):
    shutil.copy2(src_ckpt, dst_ckpt)
    sz = os.path.getsize(src_ckpt)
    print(f"  Copied W76 checkpoint -> W80 ({sz:,} bytes, 35 combos)")
else:
    print(f"  WARNING: {src_ckpt} not found!")

# W81 and W82: fresh starts, no checkpoints needed
for wid in [81, 82]:
    os.makedirs(os.path.join(CKPT_DIR, f"worker_{wid}"), exist_ok=True)

# Worker 80: [4,4,4,4] (resume from 35/70 combos) - 12g for AllSubgroups on C2^8
code_80 = make_partition_code(80,
    [[4,4,4,4]],
    "worker_80_results.txt",
    "worker_80_heartbeat.txt")
p80 = launch_worker(80, code_80, "[4,4,4,4] (35/70, optimized BFS)", mem="12g")

# Worker 81: [4,2,2,2,2,2,2] (fresh) - should be light
code_81 = make_partition_code(81,
    [[4,2,2,2,2,2,2]],
    "worker_81_results.txt",
    "worker_81_heartbeat.txt")
p81 = launch_worker(81, code_81, "[4,2,2,2,2,2,2] (fresh)", mem="4g")

# Worker 82: [3,3,3,3,2,2] (fresh) - moderate
code_82 = make_partition_code(82,
    [[3,3,3,3,2,2]],
    "worker_82_results.txt",
    "worker_82_heartbeat.txt")
p82 = launch_worker(82, code_82, "[3,3,3,3,2,2] (fresh)", mem="4g")

print(f"\nAll 3 R14 workers launched at {time.strftime('%H:%M:%S')}.")
print(f"\nStill running:")
print(f"  W43 (PID 63860): [8,8] 974/1275 combos")
print(f"  W47 (PID 55688): [8,4,4] ~689/750 combos")
print(f"  W77 (PID 76516): [4,4,4,2,2] heavy lifting")
print(f"  W78 (PID 22380): [4,4,2,2,2,2] heavy lifting")
print(f"  W79 (PID 80656): [6,4,2,2,2] combo ~62")
print(f"\nExpected completion:")
print(f"  W81 [4,2,2,2,2,2,2]: ~5-15min (small partition)")
print(f"  W82 [3,3,3,3,2,2]: ~30-120min")
print(f"  W80 [4,4,4,4]: ~30-90min (35 combos remaining, BFS now ~10s not 6h)")
