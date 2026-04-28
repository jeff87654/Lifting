"""Relaunch the 4 workers (W20-22, W26) that crashed due to GAP OutputTextFile bug.
Checkpoint files are already in place from Python-side copy."""

import subprocess
import os
import sys
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16

# Workers that failed and their partitions
FAILED_WORKERS = {
    20: [(8, 8)],
    21: [(8, 6, 2)],
    22: [(8, 4, 4)],
    26: [(6, 4, 4, 2), (9, 3, 2, 2), (10, 2, 2, 2), (5, 4, 4, 3),
         (5, 5, 4, 2), (4, 4, 3, 3, 2), (4, 3, 3, 2, 2, 2), (3, 3, 2, 2, 2, 2, 2)],
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
Print("Worker {worker_id} (relaunched) starting at ", StringTime(Runtime()), "\\n");
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
    # Clear old result/log files for failed workers
    for wid in FAILED_WORKERS:
        for suffix in ["_results.txt", ".log"]:
            f = os.path.join(OUTPUT_DIR, f"worker_{wid}{suffix}")
            if os.path.exists(f):
                os.remove(f)
                print(f"  Cleared {f}")

    # Verify checkpoint files exist
    for wid, parts in FAILED_WORKERS.items():
        ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}")
        for part in parts:
            part_str = "_".join(str(x) for x in part)
            ckpt_file = os.path.join(ckpt_dir, f"ckpt_{N}_{part_str}.g")
            if os.path.exists(ckpt_file):
                size_kb = os.path.getsize(ckpt_file) / 1024
                print(f"  W{wid} checkpoint for {list(part)}: {size_kb:.0f}KB")

    # Launch workers
    processes = {}
    for wid, parts in FAILED_WORKERS.items():
        script = create_gap_script(parts, wid)
        proc = launch_gap_worker(script, wid)
        processes[wid] = proc
        print(f"Launched W{wid} (PID {proc.pid}): {len(parts)} partitions")

    # Monitor for 90s
    print(f"\nMonitoring for 90s...")
    for tick in range(18):
        time.sleep(5)
        line = f"  [{(tick+1)*5}s]"
        for wid in sorted(processes.keys()):
            proc = processes[wid]
            rc = proc.poll()
            if rc is not None:
                line += f" W{wid}:EXIT({rc})"
                continue
            hb_path = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
            if os.path.exists(hb_path):
                with open(hb_path) as f:
                    hb = f.read().strip()[:50]
                line += f" W{wid}:{hb}"
            else:
                line += f" W{wid}:loading"
        print(line)

    print(f"\nAll relaunched. Use monitor_s16.py to track progress.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
