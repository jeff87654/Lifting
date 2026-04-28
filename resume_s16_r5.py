"""Resume S16 round 5: restart all 5 workers with raised orbital threshold.

Key optimization: Raised H^1 orbital parent threshold from 50 to 100000.
This enables orbit reduction for combos like [[4,2]^4] where parent count
explodes exponentially through abelian C_2 layers with 100% FPF acceptance.
Expected speedup: 10-70x on the stuck combos.

Checkpoint status at kill:
  W37/[8,4,4]:      573/625 combos, 74149 groups
  W38/[8,8]:         974/1275 combos, 16369 groups
  W39/[4,4,2,2,2,2]: 5/15 combos, 2154 groups (stuck on combo 6 for hours)
  W40/[4,4,4,4]:     35/70 combos, 7792 groups (stuck on combo 36 for hours)
  W41/[4,4,4,2,2]:   15/35 combos, 8805 groups (stuck on combo 16 for hours)

Remaining after current partitions:
  W39 -> [3,3,3,3,2,2]
  W40 -> [6,4,2,2,2]
  W41 -> [5,5,2,2,2], [4,2,2,2,2,2,2]
"""

import subprocess
import os
import sys
import time
import shutil

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16

# Reuse checkpoint dirs from round 4 workers
WORKERS = {
    42: {
        "old_ckpt_worker": 37,
        "partitions": [(8, 4, 4)],
    },
    43: {
        "old_ckpt_worker": 38,
        "partitions": [(8, 8)],
    },
    44: {
        "old_ckpt_worker": 39,
        "partitions": [(4, 4, 2, 2, 2, 2), (3, 3, 3, 3, 2, 2)],
    },
    45: {
        "old_ckpt_worker": 40,
        "partitions": [(4, 4, 4, 4), (6, 4, 2, 2, 2)],
    },
    46: {
        "old_ckpt_worker": 41,
        "partitions": [(4, 4, 4, 2, 2), (5, 5, 2, 2, 2), (4, 2, 2, 2, 2, 2, 2)],
    },
}


def create_gap_script(partitions, worker_id):
    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(OUTPUT_DIR, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    heartbeat_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")

    partition_strs = ["[" + ",".join(str(x) for x in p) + "]" for p in partitions]
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} (round 5 - orbital opt) starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(partitions)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

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
    processes = {}

    for wid, info in WORKERS.items():
        parts = info["partitions"]
        old_wid = info["old_ckpt_worker"]

        # Create new worker checkpoint dir
        new_ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}")
        os.makedirs(new_ckpt_dir, exist_ok=True)

        # Copy checkpoint files from old worker dir
        old_ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{old_wid}")
        if os.path.exists(old_ckpt_dir):
            for fname in os.listdir(old_ckpt_dir):
                if fname.startswith("ckpt_"):
                    src = os.path.join(old_ckpt_dir, fname)
                    dst = os.path.join(new_ckpt_dir, fname)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        print(f"  Copied checkpoint {fname} from W{old_wid} to W{wid}")
                    else:
                        print(f"  Checkpoint {fname} already exists in W{wid}")

        # Clear old results/logs for new worker
        for suffix in ["_results.txt", ".log"]:
            f = os.path.join(OUTPUT_DIR, f"worker_{wid}{suffix}")
            if os.path.exists(f):
                os.remove(f)

        script = create_gap_script(parts, wid)
        proc = launch_gap_worker(script, wid)
        processes[wid] = proc
        print(f"Launched W{wid} (PID {proc.pid}): {[list(p) for p in parts]}")

    # Monitor for 600s
    print(f"\nMonitoring for 600s...")
    for tick in range(120):
        time.sleep(5)
        line = f"  [{(tick+1)*5:3d}s]"
        all_done = True
        for wid in sorted(processes.keys()):
            proc = processes[wid]
            rc = proc.poll()
            if rc is not None:
                line += f" W{wid}:EXIT({rc})"
                continue
            all_done = False
            hb_path = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
            if os.path.exists(hb_path):
                with open(hb_path) as f:
                    hb = f.read().strip()[:60]
                line += f" W{wid}:{hb}"
            else:
                line += f" W{wid}:loading"
        print(line)
        if all_done:
            print("All workers finished!")
            break

    print(f"\nDone. 5 workers launched with orbital optimization.")
    for wid in sorted(processes.keys()):
        proc = processes[wid]
        rc = proc.poll()
        status = f"EXIT({rc})" if rc is not None else f"RUNNING (PID {proc.pid})"
        print(f"  W{wid}: {status} -> {[list(p) for p in WORKERS[wid]['partitions']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
