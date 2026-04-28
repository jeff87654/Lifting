"""Build the full S_n conjugacy class structure for n = 1..18.

Layout:
    parallel_sn/
        <n>/
            [<partition>]/
                [<combo>].g            # per-combo conjugacy class generators

Each combo .g file (matches parallel_s18 layout):
    # combo: [ [d1,k1], [d2,k2], ... ]
    # candidates: <pre-dedup count>
    # deduped: <post-dedup count>
    # elapsed_ms: <T>
    [gen1,gen2,...]                   # one subgroup per line, generators

Per degree, partitions are split across --workers GAP processes via LPT
scheduling (longest processing time first). Each worker writes per-combo
files directly; resume is automatic via the existing skip-if-complete check
at lifting_method_fast_v2.g:2724.

After each degree, we sum '# deduped:' headers across all combo files,
add inherited (OEIS A000638(n-1)), and verify against OEIS A000638(n).
Halts on mismatch.

Usage:
    python build_full_structure.py                       # 1..18, 6 workers
    python build_full_structure.py --start 14 --end 17
    python build_full_structure.py --workers 4
    python build_full_structure.py --skip-existing       # skip done degrees
"""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from math import comb
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"
OUTPUT_BASE = LIFTING / "parallel_sn"

# OEIS A000638. a(0) = 1 by convention.
OEIS = {
    0: 1,
    1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296, 9: 554, 10: 1593,
    11: 3094, 12: 10723, 13: 20832, 14: 75154, 15: 159129, 16: 686165,
    17: 1466358,
}

NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104,
    16: 1954, 17: 5, 18: 983,
}


def partitions_min_part(n, min_part=2):
    result = []
    def helper(remaining, max_part, current):
        if remaining == 0:
            result.append(tuple(current))
            return
        for i in range(min(remaining, max_part), min_part - 1, -1):
            current.append(i)
            helper(remaining - i, i, current)
            current.pop()
    helper(n, n, [])
    return result


def partition_dir_name(p):
    return "[" + ",".join(str(x) for x in p) + "]"


def gap_partition_literal(p):
    return "[" + ",".join(str(x) for x in p) + "]"


def total_combos(partition):
    """Number of factor combinations for a partition."""
    combo = 1
    counts = Counter(partition)
    for d, k in counts.items():
        t = NR_TRANSITIVE.get(d, max(1, d))
        if k == 1:
            combo *= t
        else:
            combo *= comb(t + k - 1, k)
    return max(1, combo)


def estimate_cost(partition):
    """Heuristic cost estimate for LPT scheduling.

    Combo count * per-combo base cost, with discounts for trailing 2s
    (C2 fast path) and 2-part Goursat shape.
    """
    if len(partition) == 1:
        return max(0.1, NR_TRANSITIVE.get(partition[0], 100) * 0.01)
    max_part = max(partition)
    num_2s = sum(1 for p in partition if p == 2)
    k = len(partition)
    cc = total_combos(partition)
    if max_part >= 12:
        per = max_part * 1.5
    elif max_part >= 8:
        per = max_part * 0.8
    else:
        per = max_part * 0.3
    if num_2s >= 2:
        per *= 0.3
    if k == 2 and max_part >= 5:
        per *= 0.3
    return max(0.1, cc * per)


def lpt_assign(partitions, num_workers):
    """Assign partitions to workers via LPT (longest processing time first)."""
    items = sorted(((estimate_cost(p), p) for p in partitions), reverse=True)
    workers = [[] for _ in range(num_workers)]
    loads = [0.0] * num_workers
    for cost, p in items:
        idx = loads.index(min(loads))
        workers[idx].append(p)
        loads[idx] += cost
    return workers, loads


def make_worker_script(n, worker_id, parts, out_dir, log_file):
    inherited = OEIS.get(n - 1, 0)
    parts_gap = "[" + ",".join(gap_partition_literal(p) for p in parts) + "]"
    # Heartbeat file lives alongside output. Mirrors parallel_s18 layout:
    # parallel_s18/worker_<i>_heartbeat.txt, but we use worker_<i> inside
    # the degree's output dir.
    heartbeat_file = (out_dir / f"worker_{worker_id}_heartbeat.txt").as_posix()
    return f'''
LogTo("{log_file.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("{n - 1}") := {inherited};

# Heartbeat file - LiftThroughLayer writes periodic 'alive' lines here,
# and we bracket each partition with 'starting'/'completed' markers
# mirroring parallel_s18/run_s18.py.
_HEARTBEAT_FILE := "{heartbeat_file}";
PrintTo(_HEARTBEAT_FILE, "worker {worker_id} starting n={n} partitions=",
    Length({parts_gap}), "\\n");

my_partitions := {parts_gap};
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("{out_dir.as_posix()}/[", _partStr, "]");
    Print("\\n[w{worker_id}] >> ", part, "\\n");
    PrintTo(_HEARTBEAT_FILE, "starting partition ", part, "\\n");
    fpf := FindFPFClassesForPartition({n}, part);
    Print("[w{worker_id}] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\\n");
    PrintTo(_HEARTBEAT_FILE, "completed partition ", part, " = ",
            Length(fpf), " classes (",
            Int((Runtime() - worker_start) / 1000), "s worker-total)\\n");
    total_fpf := total_fpf + Length(fpf);
od;
PrintTo(_HEARTBEAT_FILE, "worker {worker_id} done total=", total_fpf, "\\n");
Print("\\n[w{worker_id}] WORKER_TOTAL=", total_fpf, "\\n");
LogTo();
QUIT;
'''


def launch_worker(n, worker_id, parts, out_dir, env):
    log_file = LIFTING / f"build_s{n}_w{worker_id}.log"
    if log_file.exists():
        log_file.unlink()
    script = LIFTING / f"build_s{n}_w{worker_id}.g"
    script.write_text(make_worker_script(n, worker_id, parts, out_dir, log_file))
    cygwin_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/build_s{n}_w{worker_id}.g"
    proc = subprocess.Popen(
        [str(BASH_EXE), "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
         f'./gap.exe -q -o 0 "{cygwin_path}"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env, cwd=str(GAP_RUNTIME),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0)
    return proc, log_file


def sum_fpf_from_disk(out_dir, parts):
    """Sum the '# deduped: N' headers across every combo file on disk."""
    total = 0
    missing = []
    incomplete = []
    for p in parts:
        part_dir = out_dir / partition_dir_name(p)
        if not part_dir.exists():
            missing.append(partition_dir_name(p))
            continue
        files = list(part_dir.glob("*.g"))
        if not files:
            missing.append(partition_dir_name(p))
            continue
        for f in files:
            text = f.read_text()
            expected = -1
            actual = 0
            for line in text.splitlines():
                if line.startswith("# deduped: "):
                    try:
                        expected = int(line[len("# deduped: "):])
                    except ValueError:
                        expected = -1
                elif line.startswith("["):
                    actual += 1
            if expected < 0 or expected != actual:
                incomplete.append(str(f.relative_to(out_dir)))
            else:
                total += expected
    return total, missing, incomplete


def degree_complete(n):
    """True if every FPF partition of n has at least one complete combo file
    on disk. Note: this doesn't verify ALL combos are written — just that
    something exists per partition. Use sum_fpf_from_disk for the real total.
    """
    out_dir = OUTPUT_BASE / str(n)
    if not out_dir.exists():
        return False
    parts = partitions_min_part(n)
    if not parts:
        return True  # n=1
    for p in parts:
        part_dir = out_dir / partition_dir_name(p)
        if not part_dir.exists() or not list(part_dir.glob("*.g")):
            return False
    return True


def run_degree(n, num_workers, timeout_sec):
    """Compute S_n with parallel workers, return (total, elapsed)."""
    out_dir = OUTPUT_BASE / str(n)
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = partitions_min_part(n)
    for p in parts:
        (out_dir / partition_dir_name(p)).mkdir(exist_ok=True)

    inherited = OEIS.get(n - 1, 0)

    if not parts:
        # n = 1
        print(f"[S_{n}] no FPF partitions; total = inherited = {inherited}")
        return inherited, 0.0

    # LPT assignment
    workers, loads = lpt_assign(parts, num_workers)
    active = [(i, p) for i, p in enumerate(workers) if p]
    print(f"\n[S_{n}] {len(parts)} partitions split across {len(active)} worker(s)")
    for i, parts_w in active:
        names = ", ".join(partition_dir_name(p) for p in parts_w[:4])
        if len(parts_w) > 4:
            names += f", ... +{len(parts_w) - 4}"
        print(f"  worker {i}: {len(parts_w)} parts est {loads[i]:.0f}s -> {names}")

    env = os.environ.copy()
    env['PATH'] = str(GAP_RUNTIME / "bin") + os.pathsep + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    t0 = time.time()
    procs = []
    for i, parts_w in active:
        proc, log_file = launch_worker(n, i, parts_w, out_dir, env)
        procs.append((i, proc, log_file))
        print(f"  worker {i} launched (PID {proc.pid})")

    # Monitor with periodic progress
    completed = set()
    last_progress = time.time()
    while len(completed) < len(procs):
        time.sleep(15)
        for i, proc, _ in procs:
            if i in completed:
                continue
            if proc.poll() is not None:
                rc = proc.returncode
                ts = time.time() - t0
                tag = "PASS" if rc == 0 else f"rc={rc}"
                print(f"  worker {i} done ({tag}) at {ts:.0f}s")
                completed.add(i)

        # Periodic progress (every 2 min)
        if time.time() - last_progress > 120 and len(completed) < len(procs):
            ts = time.time() - t0
            running = len(procs) - len(completed)
            partial_total, _, _ = sum_fpf_from_disk(out_dir, parts)
            print(f"  [progress @ {ts:.0f}s] {running} worker(s) running, "
                  f"FPF-on-disk so far: {partial_total}")
            last_progress = time.time()

        # Hard timeout
        if time.time() - t0 > timeout_sec:
            print(f"[S_{n}] TIMEOUT after {timeout_sec}s, killing workers")
            for i, proc, _ in procs:
                if i not in completed:
                    proc.kill()
            return None, time.time() - t0

    elapsed = time.time() - t0

    # Sum from disk (authoritative)
    total_fpf, missing, incomplete = sum_fpf_from_disk(out_dir, parts)
    if missing:
        print(f"  WARNING: {len(missing)} partition(s) missing combo files: "
              f"{missing[:3]}{'...' if len(missing) > 3 else ''}")
    if incomplete:
        print(f"  WARNING: {len(incomplete)} incomplete combo file(s): "
              f"{incomplete[:3]}{'...' if len(incomplete) > 3 else ''}")

    total = inherited + total_fpf
    print(f"[S_{n}] FPF-on-disk: {total_fpf}, inherited: {inherited}, "
          f"total: {total} ({elapsed:.0f}s wall, {len(active)} workers)")
    return total, elapsed


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=18)
    parser.add_argument("--workers", type=int, default=6,
                       help="GAP workers per degree (default 6)")
    parser.add_argument("--skip-existing", action="store_true",
                       help="skip degrees that already look complete")
    parser.add_argument("--timeout", type=int, default=86400 * 14,
                       help="per-degree timeout (default 14 days)")
    args = parser.parse_args()

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    summary = []
    for n in range(args.start, args.end + 1):
        if args.skip_existing and degree_complete(n):
            # Verify against OEIS using on-disk totals
            out_dir = OUTPUT_BASE / str(n)
            parts = partitions_min_part(n)
            total_fpf, missing, incomplete = sum_fpf_from_disk(out_dir, parts)
            if missing or incomplete:
                print(f"[S_{n}] --skip-existing but {len(missing)} missing, "
                      f"{len(incomplete)} incomplete; will recompute")
            else:
                inherited = OEIS.get(n - 1, 0)
                total = inherited + total_fpf
                expected = OEIS.get(n)
                if expected is not None and total != expected:
                    print(f"[S_{n}] ON-DISK MISMATCH: {total} vs {expected}; "
                          f"investigate or rerun without --skip-existing")
                    sys.exit(1)
                print(f"[S_{n}] SKIP (on disk: {total})")
                summary.append((n, expected, "SKIP"))
                continue

        total, elapsed = run_degree(n, args.workers, args.timeout)
        expected = OEIS.get(n)

        if total is None:
            summary.append((n, expected, "TIMEOUT"))
            sys.exit(1)
        if expected is not None and total != expected:
            print(f"[S_{n}] FAIL: got {total}, expected {expected}")
            summary.append((n, expected, f"FAIL got {total}"))
            print("\n=== HALTING ON MISMATCH ===")
            print(f"Inspect parallel_sn/{n}/ and build_s{n}_w*.log to debug.")
            sys.exit(1)
        if expected is None:
            print(f"[S_{n}] computed: {total} (no OEIS reference)")
            summary.append((n, None, f"{total} ({elapsed:.0f}s)"))
        else:
            print(f"[S_{n}] PASS: {total} ({elapsed:.0f}s)")
            summary.append((n, expected, f"PASS ({elapsed:.0f}s)"))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for n, expected, status in summary:
        print(f"  S_{n:<3} {status}")


if __name__ == "__main__":
    main()
