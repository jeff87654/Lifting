"""
S16 Round 13: Relaunch 6 remaining partitions with TWO critical fixes:

1. BFS Dictionary O(n^2) bug: NewDictionary("", true) for strings uses
   DictionaryBySort with O(n) insertion. For 191K entries = O(n^2) = hours.
   FIX: Use rec() (GAP hash table) with O(1) amortized lookup/insertion.

2. CCS fast path disabled: CCS produces 65K-345K P-class reps for |P|=512-3072,
   and dedup takes hours even with Union-Find. Lifting with per-layer FPF
   pruning produces far fewer intermediates and handles these groups fine.

Workers:
  W76: [4,4,4,4] (resume from 35 combos) + [4,2,2,2,2,2,2]
  W77: [4,4,4,2,2] (resume from 16 combos) + [3,3,3,3,2,2]
  W78: [4,4,2,2,2,2] (resume from 6 combos)
  W79: [6,4,2,2,2] (resume from 61 combos)

Still running:
  W43 (PID 63860): [8,8] - 974+ combos done
  W47 (PID 55688): [8,4,4] - 682+ combos done, actively progressing
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
         f'./gap.exe -q -o 12g "{script_path}" 2>&1'],
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
Print("Worker {wid} (round 13 - BFS rec() fix + CCS disabled) starting at ", Runtime()/1000, "s\\n");
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

print(f"\n=== S16 Round 13: Launching 4 workers at {time.strftime('%H:%M:%S')} ===\n")

# Set up checkpoint directories from BEST PRE-CCS checkpoints
# IMPORTANT: Use checkpoints BEFORE CCS errors (combos 36/37 for [4,4,4,4],
# combo 7 for [4,4,2,2,2,2]) to ensure these combos are re-run with fixes.
checkpoint_sources = {
    76: ("worker_52", "ckpt_16_4_4_4_4.g"),       # [4,4,4,4]: 35 combos (pre-CCS errors)
    77: ("worker_53", "ckpt_16_4_4_4_2_2.g"),      # [4,4,4,2,2]: 16 combos
    78: ("worker_54", "ckpt_16_4_4_2_2_2_2.g"),    # [4,4,2,2,2,2]: 6 combos (pre-CCS error)
    79: ("worker_61", "ckpt_16_6_4_2_2_2.g"),      # [6,4,2,2,2]: 61 combos
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

# Worker 76: [4,4,4,4] (resume 35/70 combos, includes BFS combo) + [4,2,2,2,2,2,2] (fresh)
code_76 = make_partition_code(76,
    [[4,4,4,4], [4,2,2,2,2,2,2]],
    "worker_76_results.txt",
    "worker_76_heartbeat.txt")
p76 = launch_worker(76, code_76, "[4,4,4,4] (35/70) + [4,2,2,2,2,2,2]")

# Worker 77: [4,4,4,2,2] (resume 16/35 combos, includes BFS combo) + [3,3,3,3,2,2] (fresh)
code_77 = make_partition_code(77,
    [[4,4,4,2,2], [3,3,3,3,2,2]],
    "worker_77_results.txt",
    "worker_77_heartbeat.txt")
p77 = launch_worker(77, code_77, "[4,4,4,2,2] (16/35) + [3,3,3,3,2,2]")

# Worker 78: [4,4,2,2,2,2] (resume 6/15 combos, includes BFS combo)
code_78 = make_partition_code(78,
    [[4,4,2,2,2,2]],
    "worker_78_results.txt",
    "worker_78_heartbeat.txt")
p78 = launch_worker(78, code_78, "[4,4,2,2,2,2] (6/15)")

# Worker 79: [6,4,2,2,2] (resume 61/80 combos)
code_79 = make_partition_code(79,
    [[6,4,2,2,2]],
    "worker_79_results.txt",
    "worker_79_heartbeat.txt")
p79 = launch_worker(79, code_79, "[6,4,2,2,2] (61/80)")

print(f"\nAll 4 R13 workers launched at {time.strftime('%H:%M:%S')}.")
print(f"Still running: W43 (PID 63860, [8,8]), W47 (PID 55688, [8,4,4])")
print(f"\nExpected completion:")
print(f"  W79 [6,4,2,2,2]: ~30-60min (19 combos, now using lifting)")
print(f"  W78 [4,4,2,2,2,2]: ~1-3h (9 combos + BFS combo)")
print(f"  W77 [4,4,4,2,2]: ~2-4h (19 combos + BFS + [3,3,3,3,2,2])")
print(f"  W76 [4,4,4,4]: ~2-5h (35 combos + BFS + [4,2,2,2,2,2,2])")
