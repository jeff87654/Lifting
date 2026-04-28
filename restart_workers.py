"""Restart workers 177, 178, 180 with deduped checkpoints."""
import subprocess
import os
import time

N = 17
OUTPUT_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

WORKERS = {
    177: [8, 6, 3],
    178: [8, 4, 3, 2],
    180: [6, 4, 4, 3],
}


def make_worker_script(worker_id, partition):
    log_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(OUTPUT_DIR, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    heartbeat_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")

    part_str = "[" + ",".join(str(x) for x in partition) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} RESTARTED (deduped checkpoint) at ", StringTime(Runtime()), "\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S16)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Enable heartbeat
_HEARTBEAT_FILE := "{heartbeat_file}";

# Clear H1 cache
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

PrintTo("{heartbeat_file}", "starting partition {part_str}\\n");

partStart := Runtime();
fpf_classes := FindFPFClassesForPartition({N}, {part_str});
partTime := (Runtime() - partStart) / 1000.0;
Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");

# Save generators to per-partition file
partStr := JoinStringsWithSeparator(List({part_str}, String), "_");
genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
PrintTo(genFile, "");  # Clear any previous content
for _h_idx in [1..Length(fpf_classes)] do
    _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                  g -> ListPerm(g, {N}));
    AppendTo(genFile, String(_gens), "\\n");
od;
Print("  Generators saved to ", genFile, "\\n");

# Write count to results file (overwrite for clean restart)
PrintTo("{result_file}",
    String({part_str}), " ", String(Length(fpf_classes)), "\\n",
    "TOTAL ", String(Length(fpf_classes)), "\\n",
    "TIME ", String(partTime), "\\n");

PrintTo("{heartbeat_file}",
    "completed partition {part_str} = ", Length(fpf_classes), " classes\\n");

Print("\\nWorker {worker_id} complete: ", Length(fpf_classes), " classes in ",
      partTime, "s\\n");

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
        cwd=GAP_RUNTIME,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    return process


if __name__ == "__main__":
    # Clear old result files (they have inflated counts)
    for wid in WORKERS:
        rf = os.path.join(OUTPUT_DIR, f"worker_{wid}_results.txt")
        if os.path.exists(rf):
            os.remove(rf)
            print(f"Removed old results: worker_{wid}_results.txt")

    processes = {}
    for wid, partition in WORKERS.items():
        script_file = make_worker_script(wid, partition)
        p = launch_gap_worker(script_file, wid)
        processes[wid] = p
        print(f"Launched worker {wid} [{','.join(str(x) for x in partition)}] PID={p.pid}")

    print(f"\nAll 3 workers launched. Monitoring...")

    # Monitor loop
    while processes:
        time.sleep(60)
        done = []
        for wid, p in processes.items():
            rc = p.poll()
            hb_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
            hb = ""
            if os.path.exists(hb_file):
                try:
                    with open(hb_file, 'r') as f:
                        hb = f.read().strip()
                except:
                    pass

            res_file = os.path.join(OUTPUT_DIR, f"worker_{wid}_results.txt")
            if rc is not None:
                if os.path.exists(res_file) and os.path.getsize(res_file) > 0:
                    with open(res_file, 'r') as f:
                        print(f"  W{wid} COMPLETED (rc={rc}): {f.read().strip()}")
                else:
                    print(f"  W{wid} EXITED rc={rc} (no results)")
                done.append(wid)
            else:
                print(f"  W{wid}: {hb[:80]}")

        for wid in done:
            del processes[wid]

        if processes:
            remaining = [f"W{wid}" for wid in processes]
            print(f"  [{time.strftime('%H:%M:%S')}] {len(remaining)} running: {', '.join(remaining)}")

    print(f"\nAll workers finished at {time.strftime('%H:%M:%S')}")
