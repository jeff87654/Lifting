"""
Compute rich invariant keys for checkpoint files using parallel GAP workers.
Splits the generator list across N workers, each computes invariant keys for
its slice, then combines them and appends to the checkpoint .g file.
"""
import subprocess
import os
import sys
import time
import math

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

def count_groups(ckpt_file):
    """Count groups in checkpoint by reading the header comment."""
    with open(ckpt_file, 'r') as f:
        for line in f:
            if line.startswith('# ') and 'groups' in line:
                # Format: "# 283 combos, 75784 groups"
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == 'groups':
                        return int(parts[i-1].rstrip(','))
    return None

def create_worker_script(worker_id, ckpt_file, start_idx, end_idx, out_file):
    """Create a GAP script that computes invariant keys for groups [start..end]."""
    log_file = out_file.replace('.txt', '.log')
    # Convert paths to forward slashes for GAP
    ckpt_gap = ckpt_file.replace('\\', '/')
    out_gap = out_file.replace('\\', '/')
    log_gap = log_file.replace('\\', '/')
    lifting_gap = f"C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g"

    status_gap = out_file.replace('.txt', '_status.txt').replace('\\', '/')

    script = f'''
_rivStart := Runtime();

# Skip database loading - we only need invariant functions
SKIP_DATABASE_LOAD := true;
Read("{lifting_gap}");

PrintTo("{status_gap}", "loading_checkpoint\\n");

# Load the checkpoint generators
_CKPT_ALL_FPF_GENS := [];
_CKPT_COMPLETED_KEYS := [];
_CKPT_TOTAL_CANDIDATES := 0;
_CKPT_ADDED_COUNT := 0;
_CKPT_INV_KEYS := fail;
_CKPT_RICH_INV := false;
Read("{ckpt_gap}");

PrintTo("{status_gap}", "loaded ", Length(_CKPT_ALL_FPF_GENS), " groups\\n");

# Free memory - we only need the generators for our slice
# But we can't slice a list in-place, so just proceed

# Compute invariant keys for our slice
_keys := [];
_total := {end_idx} - {start_idx} + 1;
for _i in [{start_idx}..{end_idx}] do
    _gens := _CKPT_ALL_FPF_GENS[_i];
    if Length(_gens) > 0 then
        _H := Group(_gens);
    else
        _H := Group(());
    fi;
    _key := InvariantKey(ComputeSubgroupInvariant(_H));
    Add(_keys, _key);
    if (_i - {start_idx} + 1) mod 1000 = 0 then
        PrintTo("{status_gap}", _i - {start_idx} + 1, "/", _total,
              " (", Int((Runtime() - _rivStart)/1000), "s)\\n");
    fi;
od;

PrintTo("{status_gap}", "done ", Length(_keys), " keys in ",
      Int((Runtime() - _rivStart)/1000), "s\\n");

# Save keys to output file
PrintTo("{out_gap}", "");
for _i in [1..Length(_keys)] do
    AppendTo("{out_gap}", _keys[_i], "\\n");
od;

PrintTo("{status_gap}", "saved\\n");
QUIT;
'''
    script_file = out_file.replace('.txt', '.g')
    with open(script_file, 'w') as f:
        f.write(script)
    return script_file

def run_gap_script(script_file, timeout=7200):
    """Run a GAP script and return (stdout, stderr, returncode)."""
    script_cyg = script_file.replace('\\', '/').replace('C:/', '/cygdrive/c/')
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    process = subprocess.Popen(
        [BASH_EXE, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cyg}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=GAP_RUNTIME
    )
    return process

def compute_rich_invariants(worker_name, ckpt_file, num_workers=3, timeout=7200):
    """Compute rich invariant keys for a checkpoint using parallel workers."""
    n_groups = count_groups(ckpt_file)
    if n_groups is None:
        print(f"ERROR: Could not determine group count from {ckpt_file}")
        return False

    print(f"\n{'='*60}")
    print(f"Computing rich invariants for {worker_name}")
    print(f"Checkpoint: {ckpt_file}")
    print(f"Groups: {n_groups}, Workers: {num_workers}")
    print(f"{'='*60}")

    # Create output directory
    out_dir = os.path.join(LIFTING_DIR, "parallel_s17", f"rich_inv_{worker_name}")
    os.makedirs(out_dir, exist_ok=True)

    # Split into chunks
    chunk_size = math.ceil(n_groups / num_workers)
    workers = []
    processes = []

    for i in range(num_workers):
        start = i * chunk_size + 1  # GAP is 1-indexed
        end = min((i + 1) * chunk_size, n_groups)
        if start > n_groups:
            break

        out_file = os.path.join(out_dir, f"keys_part{i}.txt")
        script_file = create_worker_script(
            f"{worker_name}_part{i}", ckpt_file, start, end, out_file
        )
        workers.append({
            'id': i, 'start': start, 'end': end,
            'out_file': out_file, 'script_file': script_file
        })
        print(f"  Worker {i}: groups {start}..{end} ({end-start+1} groups)")

    # Launch all workers
    print(f"\nLaunching {len(workers)} workers...")
    start_time = time.time()
    for w in workers:
        proc = run_gap_script(w['script_file'], timeout)
        processes.append(proc)
        w['process'] = proc
        print(f"  Worker {w['id']} launched (PID {proc.pid})")

    # Wait for all workers with progress
    print(f"\nWaiting for workers to complete...")
    completed = [False] * len(workers)
    while not all(completed):
        time.sleep(30)
        elapsed = time.time() - start_time
        for i, w in enumerate(workers):
            if completed[i]:
                continue
            ret = w['process'].poll()
            status_file = w['out_file'].replace('.txt', '_status.txt')
            status_msg = ""
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status_msg = f.read().strip()
            if ret is not None:
                completed[i] = True
                rc_status = "OK" if ret == 0 else f"FAILED (rc={ret})"
                print(f"  Worker {i} {rc_status}: {status_msg} ({elapsed:.0f}s)")
            else:
                if status_msg:
                    print(f"  Worker {i}: {status_msg} ({elapsed:.0f}s)")

    # Check all succeeded
    for w in workers:
        if not os.path.exists(w['out_file']) or os.path.getsize(w['out_file']) == 0:
            print(f"ERROR: Worker {w['id']} produced no output!")
            return False

    # Combine keys
    print(f"\nCombining keys from {len(workers)} workers...")
    all_keys = []
    for w in workers:
        with open(w['out_file'], 'r') as f:
            keys = [line.strip() for line in f if line.strip()]
            expected = w['end'] - w['start'] + 1
            if len(keys) != expected:
                print(f"ERROR: Worker {w['id']} produced {len(keys)} keys, expected {expected}")
                return False
            all_keys.extend(keys)

    if len(all_keys) != n_groups:
        print(f"ERROR: Combined {len(all_keys)} keys, expected {n_groups}")
        return False

    print(f"Total keys: {len(all_keys)}")

    # Append _CKPT_INV_KEYS and _CKPT_RICH_INV to checkpoint file
    print(f"Appending rich invariant keys to checkpoint...")

    # Back up checkpoint first
    bak_file = ckpt_file + ".pre_rich.bak"
    import shutil
    shutil.copy2(ckpt_file, bak_file)
    print(f"  Backup: {bak_file}")

    with open(ckpt_file, 'a') as f:
        f.write("\n_CKPT_INV_KEYS := [\n")
        for i, key in enumerate(all_keys):
            f.write(f'"{key}"')
            if i < len(all_keys) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("];\n")
        f.write("\n_CKPT_RICH_INV := true;\n")

    elapsed = time.time() - start_time
    print(f"Done! {len(all_keys)} rich invariant keys written in {elapsed:.0f}s")
    return True


def launch_workers_for_partition(worker_name, ckpt_file, num_workers=3):
    """Launch GAP workers for a partition, return (workers, n_groups) or None."""
    n_groups = count_groups(ckpt_file)
    if n_groups is None:
        print(f"ERROR: Could not determine group count from {ckpt_file}")
        return None

    print(f"\n  {worker_name}: {n_groups} groups, {num_workers} workers")

    out_dir = os.path.join(LIFTING_DIR, "parallel_s17", f"rich_inv_{worker_name}")
    os.makedirs(out_dir, exist_ok=True)

    chunk_size = math.ceil(n_groups / num_workers)
    workers = []

    for i in range(num_workers):
        start = i * chunk_size + 1
        end = min((i + 1) * chunk_size, n_groups)
        if start > n_groups:
            break

        out_file = os.path.join(out_dir, f"keys_part{i}.txt")
        script_file = create_worker_script(
            f"{worker_name}_part{i}", ckpt_file, start, end, out_file
        )
        proc = run_gap_script(script_file)
        workers.append({
            'id': f"{worker_name}_p{i}", 'start': start, 'end': end,
            'out_file': out_file, 'script_file': script_file,
            'process': proc, 'name': worker_name
        })
        print(f"    Part {i}: groups {start}..{end} ({end-start+1}) PID {proc.pid}")

    return workers, n_groups


def combine_keys(workers, n_groups, ckpt_file):
    """Combine keys from workers and append to checkpoint file."""
    print(f"\n  Combining keys for {ckpt_file}...")
    all_keys = []
    for w in workers:
        if not os.path.exists(w['out_file']) or os.path.getsize(w['out_file']) == 0:
            print(f"  ERROR: Worker {w['id']} produced no output!")
            return False
        with open(w['out_file'], 'r') as f:
            keys = [line.strip() for line in f if line.strip()]
            expected = w['end'] - w['start'] + 1
            if len(keys) != expected:
                print(f"  ERROR: Worker {w['id']} produced {len(keys)} keys, expected {expected}")
                return False
            all_keys.extend(keys)

    if len(all_keys) != n_groups:
        print(f"  ERROR: Combined {len(all_keys)} keys, expected {n_groups}")
        return False

    # Back up checkpoint
    bak_file = ckpt_file + ".pre_rich.bak"
    import shutil
    shutil.copy2(ckpt_file, bak_file)
    print(f"  Backup: {bak_file}")

    # Append keys
    with open(ckpt_file, 'a') as f:
        f.write("\n_CKPT_INV_KEYS := [\n")
        for i, key in enumerate(all_keys):
            f.write(f'"{key}"')
            if i < len(all_keys) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("];\n")
        f.write("\n_CKPT_RICH_INV := true;\n")

    print(f"  {len(all_keys)} rich invariant keys written")
    return True


if __name__ == '__main__':
    ckpt_dir = os.path.join(LIFTING_DIR, "parallel_s17", "checkpoints")

    partitions = [
        ("w178", os.path.join(ckpt_dir, "worker_178", "ckpt_17_8_4_3_2.g")),
        ("w180", os.path.join(ckpt_dir, "worker_180", "ckpt_17_6_4_4_3.g")),
    ]

    print("="*60)
    print("Computing rich invariants — 6 workers in parallel")
    print("="*60)

    # Launch all 6 workers (3 per partition) simultaneously
    all_workers = []  # list of (workers, n_groups, ckpt_file)
    start_time = time.time()

    for name, ckpt in partitions:
        if not os.path.exists(ckpt):
            print(f"Checkpoint not found: {ckpt}")
            sys.exit(1)
        result = launch_workers_for_partition(name, ckpt, num_workers=3)
        if result is None:
            sys.exit(1)
        workers, n_groups = result
        all_workers.append((workers, n_groups, ckpt, name))

    flat_workers = [w for ws, _, _, _ in all_workers for w in ws]
    print(f"\n{len(flat_workers)} workers launched. Waiting...")

    # Wait for all with progress
    completed = {w['id']: False for w in flat_workers}
    while not all(completed.values()):
        time.sleep(30)
        elapsed = time.time() - start_time
        for w in flat_workers:
            if completed[w['id']]:
                continue
            ret = w['process'].poll()
            status_file = w['out_file'].replace('.txt', '_status.txt')
            status_msg = ""
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status_msg = f.read().strip()
            if ret is not None:
                completed[w['id']] = True
                rc_status = "OK" if ret == 0 else f"FAILED (rc={ret})"
                print(f"  {w['id']} {rc_status}: {status_msg} ({elapsed:.0f}s)")
            else:
                if status_msg:
                    print(f"  {w['id']}: {status_msg} ({elapsed:.0f}s)")

    elapsed = time.time() - start_time
    print(f"\nAll workers done in {elapsed:.0f}s")

    # Combine keys for each partition
    ok = True
    for workers, n_groups, ckpt, name in all_workers:
        if not combine_keys(workers, n_groups, ckpt):
            print(f"FAILED combining keys for {name}")
            ok = False

    if ok:
        print(f"\n{'='*60}")
        print(f"All checkpoints upgraded to rich invariants! ({elapsed:.0f}s)")
        print(f"{'='*60}")
    else:
        sys.exit(1)
