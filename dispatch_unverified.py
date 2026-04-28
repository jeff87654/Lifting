"""Dispatch verification reruns for top-N biggest combos in unverified
partitions. Distribute across 3 workers to parallelize."""
import os, re, subprocess
from pathlib import Path

CUR = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")

UNVERIFIED = [
    "[4,4,4,2,2,2]",
    "[4,4,4,3,3]",
    "[4,4,3,3,2,2]",
    "[4,3,3,3,3,2]",
    "[4,4,2,2,2,2,2]",
]


def parse_factors(name):
    return [(int(d), int(k)) for d, k in re.findall(r"\[(\d+),(\d+)\]", name)]


def deduped(p):
    with open(p) as f:
        for line in f:
            if line.startswith("# deduped:"):
                return int(line.split(":", 1)[1].strip())
            if line.startswith("["): return None
    return None


# Find top combos per partition (limit to TOP_N biggest)
TOP_N = 3
combos_to_run = []  # (partition_list, factor_specs, disk_count)
for pname in UNVERIFIED:
    pdir = CUR / pname
    if not pdir.exists(): continue
    parts = [int(x) for x in pname.strip("[]").split(",")]
    candidates = []
    for f in pdir.glob("*.g"):
        c = deduped(f)
        if c is not None:
            candidates.append((c, f.name))
    candidates.sort(reverse=True)
    for cnt, fname in candidates[:TOP_N]:
        factors = parse_factors(fname)
        # The factors in filename are already in canonical order matching partition
        combos_to_run.append((parts, factors, cnt, pname, fname))

print(f"Running {len(combos_to_run)} top combos:")
for c in combos_to_run:
    print(f"  {c[3]}/{c[4]}: disk={c[2]:,}")

# Distribute across 3 workers
N_WORKERS = 3
chunks = [[] for _ in range(N_WORKERS)]
for i, c in enumerate(combos_to_run):
    chunks[i % N_WORKERS].append(c)

WORKER_IDS = [820, 821, 822]
SCRIPT_PATH = "C:/Users/jeffr/Downloads/Lifting/rerun_unverified_top.g"
OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"

for wid, chunk in zip(WORKER_IDS, chunks):
    if not chunk: continue
    log_file = f"C:/Users/jeffr/Downloads/Lifting/verify_w{wid}.log"
    chunk_str = "[" + ",".join(
        f"[[{','.join(str(p) for p in c[0])}],"
        f"[{','.join(f'[{f[0]},{f[1]}]' for f in c[1])}],"
        f"{c[2]}]"
        for c in chunk
    ) + "]"
    wrapper = f"{OUTPUT_DIR}/verify_w{wid}.g"
    with open(wrapper, "w") as f:
        f.write(f'MY_LOG_FILE := "{log_file}";\n')
        f.write(f'COMBOS_TO_RUN := {chunk_str};\n')
        f.write(f'Read("{SCRIPT_PATH}");\n')
    cyg = wrapper.replace("C:/", "/cygdrive/c/")
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'
    cmd = [
        r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe",
        "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
        f'exec ./gap.exe -q -o 0 "{cyg}"'
    ]
    p = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env, cwd=r"C:\Program Files\GAP-4.15.1\runtime",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    print(f"verify_w{wid} pid={p.pid}: {len(chunk)} combos -> {log_file}")
