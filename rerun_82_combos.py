"""
Launch 4 parallel workers to rerun the 82 combos:
  - 81 entries from s18_rerun_list.txt
  - + [6,16]_[6,16]_[6,16] in [6,6,6]

Worker assignment:
  A: [6,4,4,4]   - 10 OVER     (heavy lift, biggest correction value)
  B: [8,5,5]     - 50 MISSING  (small, fast, repetitive)
  C: [6,6,6]     - 14 MISSING + [6,16]^3
  D: [10,5,3]    - 7 MISSING

Force-overwrites disk files.  Each worker writes parallel_s18/[part]/[combo].g.
"""
import os
import re
import subprocess
import sys
import time

ROOT = r"C:\Users\jeffr\Downloads\Lifting"
LOGDIR = os.path.join(ROOT, "rerun_w_logs")
os.makedirs(LOGDIR, exist_ok=True)


def parse_rerun_list():
    """Parse s18_rerun_list.txt into {partition_str: [combo_pairs, ...]}.

    Pairs are returned in PARTITION ORDER (descending by degree, ascending
    by transitive id within same degree). This matches the convention used
    by FindFPFClassesForPartition / process_combos_644_4.g, where the
    largest block sits on points 1..d_1.
    """
    by_part = {}
    path = os.path.join(ROOT, "s18_rerun_list.txt")
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = line.split()
            part_str = tokens[0]
            combo_str = tokens[1]
            pairs = []
            for chunk in combo_str.split("_"):
                m = re.match(r"\[(\d+),(\d+)\]", chunk)
                if not m:
                    raise ValueError(f"Bad combo chunk: {chunk}")
                pairs.append([int(m.group(1)), int(m.group(2))])
            # Sort to partition order: descending degree, ascending id within tie.
            pairs.sort(key=lambda p: (-p[0], p[1]))
            by_part.setdefault(part_str, []).append(pairs)
    return by_part


# Partition info: blocks (1-indexed), part list, output dir name
PARTITION_INFO = {
    "[6,4,4,4]": {"part": [6, 4, 4, 4], "blocks": [[1,6],[7,10],[11,14],[15,18]]},
    "[8,5,5]":   {"part": [8, 5, 5],    "blocks": [[1,8],[9,13],[14,18]]},
    "[6,6,6]":   {"part": [6, 6, 6],    "blocks": [[1,6],[7,12],[13,18]]},
    "[10,5,3]":  {"part": [10, 5, 3],   "blocks": [[1,10],[11,15],[16,18]]},
}

# Worker -> partition
WORKER_PART = {
    "A": "[6,4,4,4]",
    "B": "[8,5,5]",
    "C": "[6,6,6]",
    "D": "[10,5,3]",
}


def gap_list(lst):
    """Format a python list of pairs/ints as a GAP literal."""
    if not lst:
        return "[]"
    if isinstance(lst[0], list):
        return "[" + ",".join(gap_list(x) for x in lst) + "]"
    return "[" + ",".join(str(x) for x in lst) + "]"


def make_worker_g(worker_id, part_str, combos):
    """Generate a worker .g script that loads process_combos_generic.g."""
    info = PARTITION_INFO[part_str]
    out_dir = (ROOT + "/parallel_s18/" + part_str).replace("\\", "/")
    log_file = (LOGDIR + f"/worker_{worker_id}.log").replace("\\", "/")
    g_file = os.path.join(LOGDIR, f"worker_{worker_id}.g")

    body = f'''MY_WORKER_ID := "{worker_id}";
MY_LOG_FILE := "{log_file}";
MY_PART := {info["part"]};
MY_OUT_DIR := "{out_dir}";
MY_BLOCK_RANGES := {gap_list(info["blocks"])};
MY_N := 18;
MY_FORCE_OVERWRITE := true;
MY_COMBOS := {gap_list(combos)};
Read("C:/Users/jeffr/Downloads/Lifting/process_combos_generic.g");
'''
    with open(g_file, "w") as f:
        f.write(body)
    return g_file, log_file


def launch(g_file, worker_id):
    """Launch a worker GAP process in the background."""
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    cyg = "/cygdrive/c" + g_file[2:].replace("\\", "/")

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    stdout_path = os.path.join(LOGDIR, f"worker_{worker_id}.stdout")
    stderr_path = os.path.join(LOGDIR, f"worker_{worker_id}.stderr")
    stdout_f = open(stdout_path, "w")
    stderr_f = open(stderr_path, "w")

    cmd = [bash_exe, "--login", "-c",
           f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{cyg}"']
    proc = subprocess.Popen(cmd, stdout=stdout_f, stderr=stderr_f,
                            env=env, cwd=gap_runtime)
    return proc, stdout_path, stderr_path


def filter_already_done(part_str, combos, cutoff_mtime):
    """Drop combos whose disk file mtime > cutoff (already redone correctly)."""
    keep = []
    for combo in combos:
        sorted_combo = sorted(combo)
        fname = "_".join(f"[{p[0]},{p[1]}]" for p in sorted_combo) + ".g"
        fpath = os.path.join(ROOT, "parallel_s18", part_str, fname)
        if os.path.exists(fpath) and os.path.getmtime(fpath) > cutoff_mtime:
            continue
        keep.append(combo)
    return keep


def main():
    by_part = parse_rerun_list()

    # Add [6,16]^3 manually to worker C
    extra = [[6, 16], [6, 16], [6, 16]]
    by_part["[6,6,6]"].append(extra)

    # Cutoff: April 25, 2026 18:30 PT  (any file written after this is from
    # the latest correct rerun and should not be redone).
    import time
    CUTOFF = time.mktime(time.strptime("2026-04-25 18:30:00", "%Y-%m-%d %H:%M:%S"))
    for part_str in list(by_part.keys()):
        before = len(by_part[part_str])
        by_part[part_str] = filter_already_done(part_str, by_part[part_str], CUTOFF)
        after = len(by_part[part_str])
        if before != after:
            print(f"  {part_str}: {before-after} combos already redone, {after} remaining")

    print("=" * 60)
    print("Rerun assignment summary:")
    print("=" * 60)
    for w, p in WORKER_PART.items():
        n = len(by_part.get(p, []))
        print(f"  Worker {w}: {p} -> {n} combos")
    print()

    procs = []
    for worker_id, part_str in WORKER_PART.items():
        combos = by_part[part_str]
        g_file, log_file = make_worker_g(worker_id, part_str, combos)
        print(f"Launching worker {worker_id}: {part_str} ({len(combos)} combos)")
        print(f"  script: {g_file}")
        print(f"  log:    {log_file}")
        proc, sout, serr = launch(g_file, worker_id)
        procs.append((worker_id, proc, sout, serr))
        print(f"  pid:    {proc.pid}")

    print()
    print("All 4 workers launched in background.")
    print("Tail logs with: tail -f rerun_w_logs/worker_*.log")
    print("Check progress with the Bash tool / TaskList.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
