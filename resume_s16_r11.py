"""
S16 Round 11: Relaunch ALL 8 remaining partitions.

Fixes applied:
  1. _DeduplicateCCSbyConjugacy uses ComputeSubgroupInvariant for large inputs (>5000)
  2. Memory optimization: free allSubs before GF(2) BFS, free fpfRREFs during BFS
  3. Cached invariant keys for H^g lookup in CCS dedup

Status:
  47/55 partitions complete, 254,383 FPF classes so far.

  Remaining:
    [8,8]         974/1275 combos, 16369 fpf  (W43 ckpt)
    [8,4,4]       573/750 combos, 74149 fpf   (W47 ckpt)
    [4,4,4,4]     35/70 combos, 7792 fpf      (W52 ckpt) + BFS combo
    [4,4,4,2,2]   16/35 combos, 8805 fpf      (W53 ckpt) + BFS combo
    [4,4,2,2,2,2] 6/15 combos, 2154 fpf       (W54 ckpt) + BFS combo
    [6,4,2,2,2]   61/80 combos, 17091 fpf     (W61 ckpt)
    [4,2,2,2,2,2,2] - never started (5 combos + BFS)
    [3,3,3,3,2,2]   - never started (5 combos)

Workers:
  W66: [8,8] (resume from 974 combos)
  W67: [8,4,4] (resume from 573 combos)
  W68: [4,4,4,4] (resume from 35 combos) + [4,2,2,2,2,2,2]
  W69: [4,4,4,2,2] (resume from 16 combos) + [3,3,3,3,2,2]
  W70: [4,4,2,2,2,2] (resume from 6 combos)
  W71: [6,4,2,2,2] (resume from 61 combos)
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
Print("Worker {wid} (round 11 - memory fix + rich invariant dedup) starting at ", Runtime()/1000, "s\\n");
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

print(f"\n=== S16 Round 11: Launching 6 workers at {time.strftime('%H:%M:%S')} ===\n")

# Set up checkpoint directories with best available checkpoints
checkpoint_sources = {
    66: ("worker_43", "ckpt_16_8_8.g"),       # [8,8]: 974 combos
    67: ("worker_47", "ckpt_16_8_4_4.g"),      # [8,4,4]: 573 combos
    68: ("worker_52", "ckpt_16_4_4_4_4.g"),    # [4,4,4,4]: 35 combos
    69: ("worker_53", "ckpt_16_4_4_4_2_2.g"),  # [4,4,4,2,2]: 16 combos
    70: ("worker_54", "ckpt_16_4_4_2_2_2_2.g"),# [4,4,2,2,2,2]: 6 combos
    71: ("worker_61", "ckpt_16_6_4_2_2_2.g"),  # [6,4,2,2,2]: 61 combos
}

for wid, (src_worker, ckpt_file) in checkpoint_sources.items():
    ckpt_dst = os.path.join(CKPT_DIR, f"worker_{wid}")
    os.makedirs(ckpt_dst, exist_ok=True)
    src_dir = os.path.join(CKPT_DIR, src_worker)
    src_file = os.path.join(src_dir, ckpt_file)
    dst_file = os.path.join(ckpt_dst, ckpt_file)
    if os.path.exists(src_file):
        shutil.copy2(src_file, dst_file)
        sz = os.path.getsize(src_file)
        print(f"  Copied {src_worker}/{ckpt_file} -> worker_{wid}/ ({sz:,} bytes)")
    else:
        print(f"  WARNING: {src_file} not found!")

# Worker 66: [8,8] - heavy, solo worker
code_66 = make_partition_code(66,
    [[8,8]],
    "worker_66_results.txt",
    "worker_66_heartbeat.txt")
p66 = launch_worker(66, code_66, "[8,8] (resume 974/1275)")

# Worker 67: [8,4,4] - moderate, solo worker
code_67 = make_partition_code(67,
    [[8,4,4]],
    "worker_67_results.txt",
    "worker_67_heartbeat.txt")
p67 = launch_worker(67, code_67, "[8,4,4] (resume 573/750)")

# Worker 68: [4,4,4,4] (resume 35/70 + BFS) + [4,2,2,2,2,2,2] (fresh)
code_68 = make_partition_code(68,
    [[4,4,4,4], [4,2,2,2,2,2,2]],
    "worker_68_results.txt",
    "worker_68_heartbeat.txt")
p68 = launch_worker(68, code_68, "[4,4,4,4] + [4,2,2,2,2,2,2]")

# Worker 69: [4,4,4,2,2] (resume 16/35 + BFS) + [3,3,3,3,2,2] (fresh)
code_69 = make_partition_code(69,
    [[4,4,4,2,2], [3,3,3,3,2,2]],
    "worker_69_results.txt",
    "worker_69_heartbeat.txt")
p69 = launch_worker(69, code_69, "[4,4,4,2,2] + [3,3,3,3,2,2]")

# Worker 70: [4,4,2,2,2,2] (resume 6/15 + BFS)
code_70 = make_partition_code(70,
    [[4,4,2,2,2,2]],
    "worker_70_results.txt",
    "worker_70_heartbeat.txt")
p70 = launch_worker(70, code_70, "[4,4,2,2,2,2] (resume 6/15)")

# Worker 71: [6,4,2,2,2] (resume 61/80)
code_71 = make_partition_code(71,
    [[6,4,2,2,2]],
    "worker_71_results.txt",
    "worker_71_heartbeat.txt")
p71 = launch_worker(71, code_71, "[6,4,2,2,2] (resume 61/80)")

print(f"\nAll 6 R11 workers launched at {time.strftime('%H:%M:%S')}.")
print(f"Monitor: python monitor_s16.py --once")
print(f"\nExpected completion:")
print(f"  W71 [6,4,2,2,2]: ~30min (19 combos)")
print(f"  W70 [4,4,2,2,2,2]: ~1-2h (9 combos + BFS)")
print(f"  W69 [4,4,4,2,2]: ~2-4h (19 combos + BFS + [3,3,3,3,2,2])")
print(f"  W68 [4,4,4,4]: ~2-4h (35 combos + BFS + [4,2,2,2,2,2,2])")
print(f"  W67 [8,4,4]: ~3-6h (177 combos)")
print(f"  W66 [8,8]: ~6-12h (301 combos, some very heavy)")
