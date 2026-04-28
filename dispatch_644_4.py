"""Dispatch 86 missing [6,4,4,4] combos across N workers, manually assigned.

Skips W800 (already running on [6,14] combos). Splits remaining combos
([6,15] and [6,16] entirely; [6,14] partial) across workers.
"""
import os
import subprocess
from itertools import combinations_with_replacement
from pathlib import Path

OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"
PARTITION_DIR = f"{OUTPUT_DIR}/[6,4,4,4]"
SCRIPT_PATH = "C:/Users/jeffr/Downloads/Lifting/process_combos_644_4.g"

# Find missing combos
NR4 = 5
done = set()
for f in Path(PARTITION_DIR).glob("*.g"):
    done.add(f.name)

missing = []
for k6 in [14, 15, 16]:
    for ks4 in combinations_with_replacement(range(1, NR4 + 1), 3):
        a, b, c = sorted(ks4)
        name = f"[4,{a}]_[4,{b}]_[4,{c}]_[6,{k6}].g"
        if name not in done:
            # Tuple format expected: (k6, k4a, k4b, k4c)
            missing.append((k6, a, b, c))

print(f"Missing combos: {len(missing)}")
for m in missing[:10]:
    print(f"  {m}")
print(f"  ...")

# Split into N chunks
N_WORKERS = 4
chunks = [[] for _ in range(N_WORKERS)]
for i, m in enumerate(missing):
    chunks[i % N_WORKERS].append(m)

# Worker IDs 810-813 (avoid collision with W800)
WORKER_IDS = [810, 811, 812, 813]

# Launch each worker
for wid, chunk in zip(WORKER_IDS, chunks):
    if not chunk:
        continue
    log_file = f"{OUTPUT_DIR}/worker_{wid}.log"
    chunk_str = "[" + ",".join(f"[{c[0]},{c[1]},{c[2]},{c[3]}]" for c in chunk) + "]"

    # Build a wrapper GAP script that sets vars then Reads the main script
    wrapper_path = f"{OUTPUT_DIR}/worker_{wid}.g"
    with open(wrapper_path, "w") as f:
        f.write(f'MY_WORKER_ID := {wid};\n')
        f.write(f'MY_LOG_FILE := "{log_file}";\n')
        f.write(f'MY_COMBOS := {chunk_str};\n')
        f.write(f'Read("{SCRIPT_PATH}");\n')

    # Launch
    wrapper_cygwin = wrapper_path.replace("C:/", "/cygdrive/c/")
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'
    cmd = [
        r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe",
        "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
        f'exec ./gap.exe -q -o 0 "{wrapper_cygwin}"'
    ]
    p = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env, cwd=r"C:\Program Files\GAP-4.15.1\runtime",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    print(f"W{wid} pid={p.pid}: {len(chunk)} combos -> {log_file}")
    print(f"  combos: {chunk[:3]} ... {chunk[-3:]}")
