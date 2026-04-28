"""
Resume W6's remaining 8 partitions as a new worker (worker 8).
W6 crashed on [14,2] at combo 52 due to a RefineChiefSeriesLayer bug
(now fixed with IsNormal guard in lifting_algorithm.g).

Remaining partitions (in estimated cost order):
  [14,2], [7,5,4], [11,5], [13,3],
  [9,3,2,2], [4,4,3,3,2], [6,3,3,2,2], [4,4,4,2,2]
"""

import subprocess
import os
import sys
import json
import time
from pathlib import Path

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16
WORKER_ID = 13  # Combo-level CALL_WITH_CATCH wrapping entire lifting computation

PARTITIONS = [
    [14, 2],
    [13, 3],
    [11, 5],
    [7, 5, 4],
    [9, 3, 2, 2],
    [6, 3, 3, 2, 2],
    [4, 4, 3, 3, 2],
    [4, 4, 4, 2, 2],
]

def create_gap_script():
    log_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.log").replace("\\", "/")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(OUTPUT_DIR, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{WORKER_ID}").replace("\\", "/")
    heartbeat_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_heartbeat.txt").replace("\\", "/")

    partition_strs = ["[" + ",".join(str(x) for x in p) + "]" for p in PARTITIONS]
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {WORKER_ID} (W6 resume) starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(PARTITIONS)} partitions for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S15)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Enable heartbeat
_HEARTBEAT_FILE := "{heartbeat_file}";

# Clear H1 cache initially
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\n========================================\\n");
    Print("Partition ", part, ":\\n");
    partStart := Runtime();

    # Write heartbeat before starting partition
    PrintTo("{heartbeat_file}",
        "starting partition ", part, "\\n");

    fpf_classes := FindFPFClassesForPartition({N}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    # Save generators to per-partition file
    partStr := JoinStringsWithSeparator(List(part, String), "_");
    genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
    PrintTo(genFile, "");  # Clear any previous content
    for _h_idx in [1..Length(fpf_classes)] do
        _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                      g -> ListPerm(g, {N}));
        AppendTo(genFile, String(_gens), "\\n");
    od;
    Print("  Generators saved to ", genFile, "\\n");

    # Write count to results file
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");

    # Memory stats
    if IsBound(GasmanStatistics) then
        Print("  Memory: ", GasmanStatistics(), "\\n");
    fi;

    # Clear runtime caches between partitions to free memory
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    # Write heartbeat after completing partition
    PrintTo("{heartbeat_file}",
        "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {WORKER_ID} (W6 resume) complete: ", totalCount,
      " total classes in ", workerTime, "s\\n");

# Write final summary
AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

# Save FPF cache for future use
if IsBound(SaveFPFSubdirectCache) then
    SaveFPFSubdirectCache();
fi;

LogTo();
QUIT;
'''

    script_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)
    return script_file


def launch_worker(script_file):
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
    # Create checkpoint directory
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{WORKER_ID}")
    os.makedirs(ckpt_dir, exist_ok=True)

    # Create GAP script
    script_file = create_gap_script()
    print(f"Created GAP script: {script_file}")
    print(f"Partitions: {PARTITIONS}")
    print(f"Checkpoint dir: {ckpt_dir}")

    # Launch worker
    proc = launch_worker(script_file)
    print(f"Launched worker {WORKER_ID} (PID {proc.pid})")
    print(f"Log: {os.path.join(OUTPUT_DIR, f'worker_{WORKER_ID}.log')}")
    print(f"Results: {os.path.join(OUTPUT_DIR, f'worker_{WORKER_ID}_results.txt')}")
    print(f"Heartbeat: {os.path.join(OUTPUT_DIR, f'worker_{WORKER_ID}_heartbeat.txt')}")

    # Update manifest
    manifest_file = os.path.join(OUTPUT_DIR, "manifest.json")
    if os.path.exists(manifest_file):
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        # Update the partition entries to point to new worker
        for p in PARTITIONS:
            key = "_".join(str(x) for x in p)
            if key in manifest["partitions"]:
                manifest["partitions"][key]["worker_id"] = WORKER_ID
                manifest["partitions"][key]["status"] = "running"
                manifest["partitions"][key]["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)
        print("Updated manifest.json")

    # Monitor briefly
    print(f"\nMonitoring for 30s to confirm startup...")
    for i in range(6):
        time.sleep(5)
        rc = proc.poll()
        if rc is not None:
            print(f"ERROR: Worker exited with code {rc}")
            log_path = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.log")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    print("Log tail:")
                    lines = f.readlines()
                    for line in lines[-20:]:
                        print(f"  {line.rstrip()}")
            return 1

        hb_path = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_heartbeat.txt")
        if os.path.exists(hb_path):
            with open(hb_path, "r") as f:
                hb = f.read().strip()
            print(f"  [{i*5+5}s] Heartbeat: {hb}")
        else:
            print(f"  [{i*5+5}s] No heartbeat yet (loading GAP...)")

    print(f"\nWorker {WORKER_ID} running successfully (PID {proc.pid})")
    print("Use monitor_s16.py to track progress.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
