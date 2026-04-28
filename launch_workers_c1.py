"""Launch W100, W101, W102 with Phase C1 (partition normalizer) enabled."""
import subprocess
import os
import time

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
BASE = "C:/Users/jeffr/Downloads/Lifting"
PARALLEL = f"{BASE}/parallel_s16"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

workers = [
    {
        "id": 100,
        "partition": [8, 8],
        "partition_str": "8_8",
        "partition_gap": "[8,8]",
    },
    {
        "id": 101,
        "partition": [8, 4, 4],
        "partition_str": "8_4_4",
        "partition_gap": "[8,4,4]",
    },
    {
        "id": 102,
        "partition": [4, 4, 4, 4],
        "partition_str": "4_4_4_4",
        "partition_gap": "[4,4,4,4]",
    },
]

for w in workers:
    wid = w["id"]
    part_gap = w["partition_gap"]
    part_str = w["partition_str"]

    # Write GAP script using raw string to avoid escape issues
    gap_script = (
        f'LogTo("{PARALLEL}/worker_{wid}.log");\n'
        f'Print("Worker {wid} RESTARTED (Phase C1) at ", StringTime(Runtime()), "\\n");\n'
        f'Print("Partition: {part_gap}\\n\\n");\n'
        f'Read("{BASE}/lifting_method_fast_v2.g");\n'
        f'Read("{BASE}/database/lift_cache.g");\n'
        f'CHECKPOINT_DIR := "{PARALLEL}/checkpoints/worker_{wid}";\n'
        f'_HEARTBEAT_FILE := "{PARALLEL}/worker_{wid}_heartbeat.txt";\n'
        f'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
        f'PrintTo("{PARALLEL}/worker_{wid}_heartbeat.txt", "starting {part_gap} (Phase C1)\\n");\n'
        f'partStart := Runtime();\n'
        f'fpf_classes := FindFPFClassesForPartition(16, {part_gap});\n'
        f'partTime := (Runtime() - partStart) / 1000.0;\n'
        f'Print("\\n========================================\\n");\n'
        f'Print("Partition {part_gap}: ", Length(fpf_classes), " classes (", partTime, "s)\\n");\n'
        f'PrintTo("{PARALLEL}/gens/gens_{part_str}.txt", "");\n'
        f'for _h_idx in [1..Length(fpf_classes)] do\n'
        f'    AppendTo("{PARALLEL}/gens/gens_{part_str}.txt",\n'
        f'        "# Group ", _h_idx, "\\n",\n'
        f'        GeneratorsOfGroup(fpf_classes[_h_idx]), "\\n");\n'
        f'od;\n'
        f'AppendTo("{PARALLEL}/worker_{wid}_results.txt",\n'
        f'    "{part_gap}: ", String(Length(fpf_classes)),\n'
        f'    " classes (", String(Int(partTime*1000)), "ms)\\n");\n'
        f'Print("\\nWorker {wid} finished at ", StringTime(Runtime()), "\\n");\n'
        f'PrintTo("{PARALLEL}/worker_{wid}_heartbeat.txt", "DONE: {part_gap} = ", String(Length(fpf_classes)), " classes\\n");\n'
        f'LogTo();\n'
        f'QUIT;\n'
    )

    script_path = os.path.join(r"C:\Users\jeffr\Downloads\Lifting\parallel_s16", f"worker_{wid}.g")
    with open(script_path, "w") as f:
        f.write(gap_script)

    cyg_script = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.g"
    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{cyg_script}"'
    ]

    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME,
        creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    )
    print(f"Worker {wid} launched: PID {proc.pid}, partition {part_gap}")
    time.sleep(2)  # stagger launches

print("\nAll workers launched. Check heartbeat files for progress.")
