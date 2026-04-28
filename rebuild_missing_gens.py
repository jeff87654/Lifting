"""Rebuild missing gens files from checkpoint data.

For each partition with result count but no gens file, runs FindFPFClassesForPartition
with existing checkpoint. Since all combos are checkpointed, this just loads+dedup+writes.
"""
import subprocess
import os
import sys
import time
import glob

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17"
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")

# 20 partitions with results but no gens files, with expected counts
MISSING = [
    ([17], 10),
    ([15,2], 232),
    ([14,3], 231),
    ([11,2,2,2], 56),
    ([9,5,3], 1449),
    ([7,5,5], 298),
    ([7,4,4,2], 5092),
    ([7,2,2,2,2,2], 289),
    ([6,6,5], 7251),
    ([6,5,2,2,2], 5959),
    ([6,3,2,2,2,2], 8070),
    ([5,4,4,4], 25129),
    ([5,4,4,2,2], 28310),
    ([5,4,3,3,2], 5607),
    ([5,4,2,2,2,2], 6956),
    ([5,3,3,3,3], 481),
    ([5,2,2,2,2,2,2], 681),
    ([4,3,2,2,2,2,2], 9086),
    ([3,3,3,3,3,2], 424),
    ([3,2,2,2,2,2,2,2], 653),
]

# Find checkpoint dir for each partition
def find_checkpoint_dir(partition):
    """Find the checkpoint directory containing data for this partition."""
    part_str = "_".join(str(x) for x in partition)
    g_name = f"ckpt_17_{part_str}.g"
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    best_dir = None
    best_size = 0
    for entry in os.listdir(ckpt_base):
        d = os.path.join(ckpt_base, entry)
        if not os.path.isdir(d):
            continue
        gfile = os.path.join(d, g_name)
        if os.path.exists(gfile):
            sz = os.path.getsize(gfile)
            if sz > best_size:
                best_size = sz
                best_dir = d
    return best_dir

def run_batch(partitions_batch, batch_id):
    """Run a batch of partitions through a single GAP process."""
    log_file = f"C:/Users/jeffr/Downloads/Lifting/rebuild_gens_{batch_id}.log"
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/rebuild_gens_{batch_id}.g"
    script_win = rf"C:\Users\jeffr\Downloads\Lifting\rebuild_gens_{batch_id}.g"

    lines = []
    lines.append(f'LogTo("{log_file}");')
    lines.append('Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");')
    lines.append('Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");')
    lines.append("")

    for partition, expected in partitions_batch:
        part_str = "_".join(str(x) for x in partition)
        ckpt_dir = find_checkpoint_dir(partition)
        if not ckpt_dir:
            print(f"  WARNING: No checkpoint dir for {partition}, skipping")
            continue

        ckpt_dir_gap = ckpt_dir.replace("\\", "/")
        gens_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_{part_str}.txt"

        lines.append(f'Print("\\n=== Rebuilding {partition} ===\\n");')
        lines.append(f'CHECKPOINT_DIR := "{ckpt_dir_gap}";')
        lines.append(f'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;')
        lines.append(f'_fpf := FindFPFClassesForPartition(17, {partition});')
        lines.append(f'Print("  Got ", Length(_fpf), " classes (expected {expected})\\n");')
        lines.append(f'if Length(_fpf) <> {expected} then')
        lines.append(f'    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected {expected}\\n");')
        lines.append(f'fi;')
        # Write gens file
        lines.append(f'_genFile := "{gens_file}";')
        lines.append(f'PrintTo(_genFile, "");')
        lines.append(f'for _h_idx in [1..Length(_fpf)] do')
        lines.append(f'    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));')
        lines.append(f'    AppendTo(_genFile, String(_gens), "\\n");')
        lines.append(f'od;')
        lines.append(f'Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\\n");')
        lines.append("")

    lines.append("LogTo();")
    lines.append("QUIT;")

    with open(script_win, "w") as f:
        f.write("\n".join(lines))

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print(f"  Launching GAP batch {batch_id} with {len(partitions_batch)} partitions...")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 4g "{script_path}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )
    return process, log_file


if __name__ == "__main__":
    print(f"Rebuilding {len(MISSING)} missing gens files from checkpoints")
    print(f"Start time: {time.strftime('%H:%M:%S')}")

    # Split into batches to parallelize (4 batches for 4 parallel GAP processes)
    n_batches = 4
    batches = [[] for _ in range(n_batches)]
    for i, item in enumerate(MISSING):
        batches[i % n_batches].append(item)

    processes = []
    for bid, batch in enumerate(batches):
        if not batch:
            continue
        proc, logf = run_batch(batch, bid)
        processes.append((proc, logf, bid, batch))

    # Monitor
    while True:
        all_done = True
        for proc, logf, bid, batch in processes:
            rc = proc.poll()
            if rc is None:
                all_done = False
                # Show progress
                if os.path.exists(logf):
                    with open(logf, "r", errors="replace") as f:
                        content = f.read()
                    rebuilding = content.count("=== Rebuilding")
                    wrote = content.count("Wrote ")
                    warnings = content.count("WARNING")
                    print(f"  Batch {bid}: {wrote}/{len(batch)} done, {warnings} warnings")
                else:
                    print(f"  Batch {bid}: starting...")
            else:
                if os.path.exists(logf):
                    with open(logf, "r", errors="replace") as f:
                        content = f.read()
                    wrote = content.count("Wrote ")
                    warnings = content.count("WARNING")
                    print(f"  Batch {bid}: FINISHED (rc={rc}, {wrote}/{len(batch)} wrote, {warnings} warnings)")

        if all_done:
            break
        time.sleep(30)

    print(f"\nDone at {time.strftime('%H:%M:%S')}")

    # Verify all gens files now exist
    missing_still = []
    for partition, expected in MISSING:
        part_str = "_".join(str(x) for x in partition)
        gens_file = os.path.join(GENS_DIR, f"gens_{part_str}.txt")
        if os.path.exists(gens_file) and os.path.getsize(gens_file) > 0:
            with open(gens_file, "r") as f:
                count = sum(1 for line in f if line.strip().startswith("["))
            status = "OK" if count == expected else f"MISMATCH ({count} vs {expected})"
            print(f"  {partition}: {count} groups - {status}")
        else:
            missing_still.append(partition)
            print(f"  {partition}: STILL MISSING!")

    if missing_still:
        print(f"\n{len(missing_still)} partitions still missing gens files!")
    else:
        print(f"\nAll 20 gens files rebuilt successfully!")
