"""Resume S16 round 4: kill-and-resume all 5 active workers from checkpoint.

Remaining 9 partitions (5 in-progress + 4 not-started):
  In-progress (with checkpoint):
    [8,4,4]:      516/625 combos, 64261 groups (W22 -> W37)
    [8,8]:        957/1275 combos, 15733 groups (W30 -> W38)
    [4,4,2,2,2,2]: 3/15 combos, 1948 groups (W32 -> W39)
    [4,4,4,4]:     28/70 combos, 7577 groups (W34 -> W40)
    [4,4,4,2,2]:   10/35 combos, 7856 groups (W35 -> W41)
  Not started:
    [3,3,3,3,2,2]   (W39 after [4,4,2,2,2,2])
    [6,4,2,2,2]     (W40 after [4,4,4,4])
    [5,5,2,2,2]     (W41 after [4,4,4,2,2])
    [4,2,2,2,2,2,2] (W41 after [5,5,2,2,2])

Key change: checkpoint now saves after EVERY combo (not every 60s).
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

# Map: new_worker_id -> (old_worker_id_for_checkpoint, partitions_list)
WORKERS = {
    37: {
        "old_ckpt_worker": 22,
        "partitions": [(8, 4, 4)],
    },
    38: {
        "old_ckpt_worker": 30,
        "partitions": [(8, 8)],
    },
    39: {
        "old_ckpt_worker": 32,
        "partitions": [(4, 4, 2, 2, 2, 2), (3, 3, 3, 3, 2, 2)],
    },
    40: {
        "old_ckpt_worker": 34,
        "partitions": [(4, 4, 4, 4), (6, 4, 2, 2, 2)],
    },
    41: {
        "old_ckpt_worker": 35,
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
Print("Worker {worker_id} (round 4 - resume) starting at ", StringTime(Runtime()), "\\n");
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
                    # Only copy checkpoints for partitions this worker handles
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

    # Monitor for 300s
    print(f"\nMonitoring for 300s...")
    for tick in range(60):
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

    print(f"\nDone. 5 workers launched for 9 remaining partitions (resuming from checkpoint).")
    for wid in sorted(processes.keys()):
        proc = processes[wid]
        rc = proc.poll()
        status = f"EXIT({rc})" if rc is not None else f"RUNNING (PID {proc.pid})"
        print(f"  W{wid}: {status} -> {[list(p) for p in WORKERS[wid]['partitions']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
