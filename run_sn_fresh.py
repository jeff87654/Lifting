"""run_sn_fresh.py - fresh full computation of S_1..S_19 conjugacy class
subgroups via Holt's method.

Bottom-up by degree. Each degree's combo files become the input catalog used
by higher-degree combos. Per-combo dispatch:

  atom            (single species, mult=1, e.g. [d,t])
                  -> direct GAP write of T(d,t) generators
  distinguished   (>=1 species mult=1 with rest)
                  -> predict_2factor.py mode=distinguished --emit-generators
  holt_split      (>=2 species, all mult>=2)
                  -> predict_2factor.py mode=holt_split --emit-generators
                     (or predict_holt_split.py)
  burnside_m2     (single species, mult=2)
                  -> predict_2factor.py mode=burnside_m2 --emit-generators
  lifting         (single species, mult>=3, e.g. [2,1]^k)
                  -> GAP single-combo lifting (uses C2 linalg path
                     via HasSmallAbelianization gate when applicable)

OEIS validation gate after each degree. No cross-combo dedup needed
(subdirect product structure is itself a conjugacy invariant).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================
ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
OUTPUT_DIR = ROOT / "parallel_sn_fresh"
H_CACHE_DIR = OUTPUT_DIR / "_h_cache"
TMP_PRED = OUTPUT_DIR / "_predict_tmp"
TMP_HOLT_SPLIT = OUTPUT_DIR / "_predict_holt_split_tmp"
LOG_DIR = OUTPUT_DIR / "_logs"

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"

PREDICT_2FACTOR = ROOT / "predict_2factor.py"
PREDICT_HOLT_SPLIT = ROOT / "predict_holt_split.py"

# OEIS A000638 - total subgroups of S_n up to conjugacy
A000638 = {
    1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296, 9: 554,
    10: 1593, 11: 3094, 12: 10723, 13: 20832, 14: 75154, 15: 159129,
    16: 686165, 17: 1466358, 18: 7274651,
    # 19: unknown
}

NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50, 9: 34, 10: 45,
    11: 8, 12: 301, 13: 9, 14: 63, 15: 104, 16: 1954, 17: 5, 18: 983, 19: 8,
}


# ============================================================================
# Path / conversion helpers
# ============================================================================
def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def part_dir_name(p) -> str:
    return "[" + ",".join(str(x) for x in p) + "]"


def combo_filename(c) -> str:
    return "_".join(f"[{d},{t}]" for d, t in sorted(c))


def combo_path(n: int, p, c) -> Path:
    return OUTPUT_DIR / str(n) / part_dir_name(p) / f"{combo_filename(c)}.g"


# ============================================================================
# Partition + combo enumeration
# ============================================================================
def fpf_partitions(n: int):
    """All partitions of n with parts >= 2, descending order."""
    if n < 2:
        return []
    out = []

    def rec(rem, mx, cur):
        if rem == 0:
            out.append(tuple(cur))
            return
        for p in range(min(rem, mx), 1, -1):
            cur.append(p)
            rec(rem - p, p, cur)
            cur.pop()

    rec(n, n, [])
    return out


def multisets(n_t: int, k: int):
    """All non-decreasing k-tuples from {1..n_t}."""
    out = []

    def rec(start, rem, cur):
        if rem == 0:
            out.append(tuple(cur))
            return
        for i in range(start, n_t + 1):
            cur.append(i)
            rec(i, rem - 1, cur)
            cur.pop()

    rec(1, k, [])
    return out


def enumerate_combos(partition):
    """For partition like (4, 2, 2): for each distinct part d, choose a
    multiset of t-indices of size = count(d). Cross-product across distinct
    parts. Returns list of combos, each a tuple of (d, t) sorted by (d, t).
    """
    counts = Counter(partition)
    distinct_ds = sorted(counts.keys())
    per_d_choices = {d: multisets(NR_TRANSITIVE[d], counts[d]) for d in distinct_ds}
    combos = []

    def rec(i, cur):
        if i == len(distinct_ds):
            combos.append(tuple(sorted(cur)))
            return
        d = distinct_ds[i]
        for choice in per_d_choices[d]:
            new = cur + [(d, t) for t in choice]
            rec(i + 1, new)

    rec(0, [])
    return combos


def classify_combo(combo) -> str:
    """One of: atom, distinguished, holt_split, lifting.

    Note: predict_2factor's burnside_m2 mode has a known bug in
    --emit-generators (emits all orbits instead of (orbits+swap_fixed)/2
    swap-equivalence reps). Single-species mult=2 combos are routed to
    'lifting' instead, which produces correctly-deduped files.
    """
    clusters = Counter(combo)
    if len(clusters) == 1:
        sp, mult = next(iter(clusters.items()))
        if mult == 1:
            return "atom"
        return "lifting"  # mult >= 2 (was burnside_m2 for mult==2)
    if any(m == 1 for m in clusters.values()):
        return "distinguished"
    return "holt_split"


# ============================================================================
# Combo file I/O
# ============================================================================
def count_subgroups_in_combo_file(path: Path):
    """Count non-comment lines starting with '[' in a combo file."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for line in f if line.lstrip().startswith("["))


def write_combo_file(path: Path, combo, gens_lines, elapsed_ms):
    """Write a combo file in the parallel_sn format.

    gens_lines: list of strings, each a complete `[gens]` line (no trailing
                newline).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    combo_repr = "[ " + ", ".join(f"[ {d}, {t} ]" for d, t in sorted(combo)) + " ]"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# combo: {combo_repr}\n")
        f.write(f"# candidates: {len(gens_lines)}\n")
        f.write(f"# deduped: {len(gens_lines)}\n")
        f.write(f"# elapsed_ms: {int(elapsed_ms)}\n")
        for g in gens_lines:
            f.write(g.rstrip("\n") + "\n")


# ============================================================================
# GAP runner
# ============================================================================
def run_gap(script_path: Path, timeout=None):
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(script_path)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True,
                             timeout=timeout, cwd=GAP_RUNTIME)
        return res.returncode == 0, time.time() - t0, res.stderr
    except subprocess.TimeoutExpired:
        return False, time.time() - t0, "timeout"


# ============================================================================
# Atom production - one batched GAP call for all (d, t) atom files
# ============================================================================
def produce_atoms(degrees):
    """Generate [d,t].g atom files for all d in degrees, t in 1..NrTransitive(d).
    One batched GAP call. Each file contains a single line: [T(d,t) generators].
    Skips atoms whose files already exist.
    """
    # Plan all writes
    todo = []
    for d in degrees:
        for t in range(1, NR_TRANSITIVE[d] + 1):
            outfile = combo_path(d, (d,), ((d, t),))
            if outfile.exists():
                continue
            outfile.parent.mkdir(parents=True, exist_ok=True)
            todo.append((d, t, outfile))

    if not todo:
        print(f"[atoms] all atoms already present, skipping")
        return True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    script = LOG_DIR / "_produce_atoms.g"
    log = LOG_DIR / "_produce_atoms.log"

    lines = [f'LogTo("{to_cyg(log)}");']
    for d, t, outfile in todo:
        outfile_cyg = to_cyg(outfile)
        lines.append(f'_T := TransitiveGroup({d}, {t});')
        lines.append(f'_gens := GeneratorsOfGroup(_T);')
        lines.append(f'PrintTo("{outfile_cyg}", "# combo: [ [ {d}, {t} ] ]\\n");')
        lines.append(f'AppendTo("{outfile_cyg}", "# candidates: 1\\n");')
        lines.append(f'AppendTo("{outfile_cyg}", "# deduped: 1\\n");')
        lines.append(f'AppendTo("{outfile_cyg}", "# elapsed_ms: 0\\n");')
        lines.append(f'AppendTo("{outfile_cyg}", "[", '
                     f'JoinStringsWithSeparator(List(_gens, String), ","), "]\\n");')
    lines.append('LogTo();')
    lines.append('QUIT;')

    script.write_text("\n".join(lines), encoding="utf-8")
    print(f"[atoms] producing {len(todo)} atom files in one GAP batch...")
    ok, elapsed, err = run_gap(script)
    print(f"[atoms] {'OK' if ok else 'FAIL'} in {elapsed:.1f}s")
    if not ok:
        print(f"[atoms] stderr: {err[:500]}")
        return False
    # Verify all files were created
    missing = [t for t in todo if not t[2].exists()]
    if missing:
        print(f"[atoms] FAIL: {len(missing)} atom files not created")
        return False
    return True


# ============================================================================
# predict_2factor invocation (per-combo)
# ============================================================================
def predict_2factor_env(worker_id=None):
    """Env for predict_2factor.py with our SN_DIR / cache paths.
    If worker_id is set, gives each worker its own H-cache + TMP shard so
    workers don't race on shared files.
    """
    env = os.environ.copy()
    env["PREDICT_SN_DIR"] = str(OUTPUT_DIR)
    if worker_id is not None:
        env["PREDICT_TMP_DIR"] = str(TMP_PRED / f"worker_{worker_id}")
        env["PREDICT_H_CACHE_DIR"] = str(H_CACHE_DIR / f"worker_{worker_id}")
        env["PREDICT_HOLT_SPLIT_TMP_DIR"] = str(
            TMP_HOLT_SPLIT / f"worker_{worker_id}")
    else:
        env["PREDICT_TMP_DIR"] = str(TMP_PRED)
        env["PREDICT_H_CACHE_DIR"] = str(H_CACHE_DIR)
        env["PREDICT_HOLT_SPLIT_TMP_DIR"] = str(TMP_HOLT_SPLIT)
    return env


def run_predict_2factor(combo, mode, worker_id=None, timeout=3600):
    """Shell out to predict_2factor.py --emit-generators for one combo.
    Returns (success, count, fps_path, elapsed_s, error_msg)."""
    combo_str = combo_filename(combo)
    cmd = [sys.executable, str(PREDICT_2FACTOR),
           "--combo", combo_str,
           "--mode", mode,
           "--emit-generators",
           "--force",
           "--timeout", str(timeout)]
    env = predict_2factor_env(worker_id=worker_id)
    t0 = time.time()
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True,
                             timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return False, 0, None, time.time() - t0, "subprocess timeout"
    elapsed = time.time() - t0
    if res.returncode != 0:
        return False, 0, None, elapsed, f"returncode={res.returncode}: {res.stderr[:500]}"
    # Parse stdout JSON
    try:
        out = json.loads(res.stdout)
    except json.JSONDecodeError:
        return False, 0, None, elapsed, f"non-JSON output: {res.stdout[:500]}"
    if "error" in out:
        return False, 0, None, elapsed, str(out["error"])
    fps_path = out.get("generators_file")
    return True, int(out["predicted"]), fps_path, elapsed, None


def fps_to_combo_file(fps_path: Path, dest: Path, combo, elapsed_ms):
    """Convert predict_2factor's fps.g output to the parallel_sn combo file
    format at dest."""
    if fps_path is None or not Path(fps_path).exists():
        return False, "fps.g missing"
    text = Path(fps_path).read_text(encoding="utf-8", errors="ignore")
    gens_lines = [ln.rstrip()
                  for ln in text.splitlines()
                  if ln.lstrip().startswith("[")]
    write_combo_file(dest, combo, gens_lines, elapsed_ms)
    return True, None


def produce_combo_via_predict(n: int, partition, combo, mode, worker_id=None):
    """Run predict_2factor for combo, write parallel_sn-format file at
    combo_path(n, partition, combo). Returns (count, elapsed_s, error)."""
    dest = combo_path(n, partition, combo)
    if dest.exists():
        return count_subgroups_in_combo_file(dest), 0.0, None
    ok, count, fps_path, elapsed, err = run_predict_2factor(
        combo, mode, worker_id=worker_id)
    if not ok:
        return None, elapsed, err
    ok2, err2 = fps_to_combo_file(Path(fps_path), dest, combo, elapsed * 1000)
    if not ok2:
        return None, elapsed, err2
    actual = count_subgroups_in_combo_file(dest)
    if actual != count:
        return None, elapsed, f"count mismatch: predict={count} file={actual}"
    return actual, elapsed, None


# ============================================================================
# Worker function (top-level for ProcessPoolExecutor on Windows)
# ============================================================================
def worker_compute_combo(args):
    """Top-level pickleable function for ProcessPoolExecutor.
    args: (n, partition_tuple, combo_tuple, classification, worker_id)
    Returns: (n, partition, combo, cls, count_or_None, elapsed_s, error_or_None)
    """
    n, partition, combo, cls, worker_id = args
    if cls in ("distinguished", "holt_split", "burnside_m2"):
        cnt, elapsed, err = produce_combo_via_predict(
            n, partition, combo, cls, worker_id=worker_id)
    elif cls == "lifting":
        cnt, elapsed, err = produce_combo_via_lifting(n, partition, combo)
    elif cls == "atom":
        cnt = count_subgroups_in_combo_file(combo_path(n, partition, combo))
        elapsed = 0.0
        err = None if cnt is not None else "atom file missing"
    else:
        cnt, elapsed, err = None, 0.0, f"unknown class {cls}"
    return (n, partition, combo, cls, cnt, elapsed, err)


# ============================================================================
# Lifting fallback (single-species mult>=3, e.g. [2,1]^k)
# ============================================================================
def produce_combo_via_lifting(n: int, partition, combo):
    """Compute one combo via FindFPFClassesForPartition (which internally
    iterates all combos for the partition). Extracts only the requested
    combo's count + writes its file.

    Phase 1 implementation: run lifting for the WHOLE partition once,
    let GAP write per-combo files via COMBO_OUTPUT_DIR, return our combo's
    count. Wasteful if the partition has many combos but only one is
    'lifting' class - but in practice partitions with mult>=3 single-species
    combos tend to BE that single combo (e.g. [2]^k -> [2,1]^k).
    """
    dest = combo_path(n, partition, combo)
    if dest.exists():
        return count_subgroups_in_combo_file(dest), 0.0, None

    # Partition output dir for COMBO_OUTPUT_DIR
    part_dir = dest.parent
    part_dir.mkdir(parents=True, exist_ok=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    script = LOG_DIR / f"_lifting_{n}_{part_dir_name(partition)}.g"
    log = LOG_DIR / f"_lifting_{n}_{part_dir_name(partition)}.log"

    part_gap = "[" + ",".join(str(x) for x in partition) + "]"
    gap_code = f'''LogTo("{to_cyg(log)}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Holt engine + iso-transport disabled (matches run_s18.py settings)
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;

# Per-combo output goes here
COMBO_OUTPUT_DIR := "{to_cyg(part_dir)}";

FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_classes := FindFPFClassesForPartition({n}, {part_gap});
Print("LIFTING_RESULT n=", {n}, " partition=", {part_gap},
      " count=", Length(_classes), "\\n");
LogTo();
QUIT;
'''
    script.write_text(gap_code, encoding="utf-8")
    t0 = time.time()
    ok, elapsed, err = run_gap(script)
    if not ok:
        return None, elapsed, f"lifting GAP failed: {err[:500]}"
    if not dest.exists():
        return None, elapsed, f"combo file not produced at {dest}"
    return count_subgroups_in_combo_file(dest), elapsed, None


# ============================================================================
# Per-degree processing
# ============================================================================
def process_degree(n: int, inherited: int, n_workers: int = 1):
    """Produce all FPF combos for degree n, return summary dict.

    Dispatch logic:
      - Atoms counted immediately (already produced upfront).
      - Partitions containing any 'lifting' combo: run partition-level lifting
        once; this writes per-combo files for ALL combos in the partition
        (avoids duplicate work and inter-worker file races).
      - Other combos: parallel via ProcessPoolExecutor when n_workers > 1.
    """
    t0 = time.time()
    partitions = fpf_partitions(n)
    fpf_total = 0
    partition_results = {p: {"count": 0, "n_combos": 0, "failed": False}
                        for p in (part_dir_name(P) for P in partitions)}
    failures = []
    combo_tasks = []          # (n, P, c, cls) for parallel pool
    partition_lifting = []    # P for partition-level lifting

    # Phase A: classify everything
    for P in partitions:
        combos = enumerate_combos(P)
        partition_results[part_dir_name(P)]["n_combos"] = len(combos)
        has_lifting = any(classify_combo(c) == "lifting" for c in combos)
        if has_lifting:
            partition_lifting.append(P)
        else:
            for c in combos:
                cls = classify_combo(c)
                if cls == "atom":
                    cnt = count_subgroups_in_combo_file(combo_path(n, P, c))
                    if cnt is None:
                        failures.append((P, c, cls, "atom file missing"))
                        partition_results[part_dir_name(P)]["failed"] = True
                    else:
                        partition_results[part_dir_name(P)]["count"] += cnt
                        fpf_total += cnt
                else:
                    combo_tasks.append((n, P, c, cls))

    # Phase B: partition-level lifting (sequential - heavy GAP jobs)
    for P in partition_lifting:
        combos = enumerate_combos(P)
        # Run lifting once for the whole partition (writes all combo files).
        # We pass the first non-atom combo just to trigger; lifting writes all.
        non_atom = [c for c in combos if classify_combo(c) != "atom"]
        if non_atom:
            cnt0, elapsed, err = produce_combo_via_lifting(n, P, non_atom[0])
            if err:
                print(f"  [{n}] {part_dir_name(P)} (partition-lifting) "
                      f"FAILED: {err}")
                failures.append((P, non_atom[0], "lifting", err))
                partition_results[part_dir_name(P)]["failed"] = True
                continue
        # Sum counts from all combo files in this partition
        psum = 0
        for c in combos:
            cnt = count_subgroups_in_combo_file(combo_path(n, P, c))
            if cnt is None:
                failures.append((P, c, classify_combo(c),
                                 "combo file missing after lifting"))
                partition_results[part_dir_name(P)]["failed"] = True
                continue
            psum += cnt
            print(f"  [{n}] {part_dir_name(P)} {combo_filename(c)} "
                  f"({classify_combo(c)}) = {cnt}")
        partition_results[part_dir_name(P)]["count"] = psum
        fpf_total += psum
        print(f"  [{n}] {part_dir_name(P)} subtotal = {psum} "
              f"({len(combos)} combos, partition-lifting)")

    # Phase C: combo-level via predict_2factor (parallel or sequential)
    if combo_tasks:
        if n_workers > 1:
            # Parallel via ProcessPoolExecutor; each task tagged with worker id
            tagged = [(t[0], t[1], t[2], t[3], i % n_workers)
                      for i, t in enumerate(combo_tasks)]
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                futs = {pool.submit(worker_compute_combo, t): t for t in tagged}
                done = 0
                for fut in as_completed(futs):
                    done += 1
                    n_, P, c, cls, cnt, elapsed, err = fut.result()
                    if cnt is None:
                        print(f"  [{n_}] {part_dir_name(P)} "
                              f"{combo_filename(c)} ({cls}) FAILED: {err}")
                        failures.append((P, c, cls, err))
                        partition_results[part_dir_name(P)]["failed"] = True
                    else:
                        partition_results[part_dir_name(P)]["count"] += cnt
                        fpf_total += cnt
                        print(f"  [{n_}] [{done}/{len(combo_tasks)}] "
                              f"{part_dir_name(P)} {combo_filename(c)} "
                              f"({cls}) = {cnt} ({elapsed:.1f}s)")
        else:
            # Sequential
            for n_, P, c, cls in combo_tasks:
                cnt, elapsed, err = produce_combo_via_predict(n_, P, c, cls)
                if cnt is None:
                    print(f"  [{n_}] {part_dir_name(P)} "
                          f"{combo_filename(c)} ({cls}) FAILED: {err}")
                    failures.append((P, c, cls, err))
                    partition_results[part_dir_name(P)]["failed"] = True
                else:
                    partition_results[part_dir_name(P)]["count"] += cnt
                    fpf_total += cnt
                    print(f"  [{n_}] {part_dir_name(P)} "
                          f"{combo_filename(c)} ({cls}) = {cnt} "
                          f"({elapsed:.1f}s)")

    # Per-partition summary
    for P in partitions:
        pr = partition_results[part_dir_name(P)]
        if part_dir_name(P) not in [part_dir_name(p) for p in partition_lifting]:
            print(f"  [{n}] {part_dir_name(P)} subtotal = {pr['count']} "
                  f"({pr['n_combos']} combos)")

    return {
        "n": n,
        "inherited": inherited,
        "fpf": fpf_total,
        "total": inherited + fpf_total,
        "partitions": partition_results,
        "failures": [
            {"partition": list(P), "combo": combo_filename(c),
             "class": cls, "error": str(err)}
            for P, c, cls, err in failures
        ],
        "elapsed_s": time.time() - t0,
    }


def write_manifest(n: int, result: dict):
    OUTPUT_DIR.joinpath(str(n)).mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT_DIR / str(n) / "manifest.json"
    payload = {
        **result,
        "expected_total": A000638.get(n),
        "match_oeis": (A000638.get(n) == result["total"]) if n in A000638 else None,
        "created": datetime.datetime.now().isoformat(),
    }
    manifest_path.write_text(json.dumps(payload, indent=2))


# ============================================================================
# Main
# ============================================================================
def parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-n", type=int, default=19,
                    help="Maximum degree to compute (default: 19)")
    ap.add_argument("--min-n", type=int, default=1,
                    help="Starting degree (default: 1)")
    ap.add_argument("--workers", type=int, default=6,
                    help="Worker count for per-combo parallelism (default: 6)")
    ap.add_argument("--skip-atoms", action="store_true",
                    help="Skip atom production (assume atoms already exist)")
    ap.add_argument("--continue-on-mismatch", action="store_true",
                    help="Don't halt on OEIS gate failure")
    ap.add_argument("--clean", action="store_true",
                    help="Wipe parallel_sn_fresh/ before starting")
    return ap.parse_args()


def main():
    args = parse_args()

    if args.clean and OUTPUT_DIR.exists():
        print(f"[clean] removing {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: produce atoms upfront (d>=2; d=1 has no FPF partition)
    if not args.skip_atoms:
        if not produce_atoms(range(2, args.max_n + 1)):
            print("[FATAL] atom production failed")
            sys.exit(1)

    # Step 2: per-degree processing with OEIS gate
    cumulative_total = 1  # FPF(0) = 1 (the trivial group of S_0)
    summary = {}
    overall_t0 = time.time()

    for n in range(args.min_n, args.max_n + 1):
        print(f"\n========== S_{n} (inherited={cumulative_total}, "
              f"workers={args.workers}) ==========")
        result = process_degree(n, cumulative_total, n_workers=args.workers)
        summary[n] = result
        write_manifest(n, result)

        # OEIS gate
        if n in A000638:
            expected = A000638[n]
            if result["total"] == expected:
                print(f"[OEIS] S_{n} = {result['total']} OK "
                      f"(elapsed {result['elapsed_s']:.1f}s)")
            else:
                print(f"[OEIS] S_{n} = {result['total']} != {expected} "
                      f"(MISMATCH, delta = {result['total'] - expected})")
                if not args.continue_on_mismatch:
                    print("[FATAL] OEIS gate failed; halting (use "
                          "--continue-on-mismatch to override)")
                    sys.exit(1)
        else:
            print(f"[OEIS] S_{n} = {result['total']} (no reference value)")

        cumulative_total = result["total"]

    elapsed = time.time() - overall_t0
    print(f"\n=== Summary (elapsed {elapsed:.1f}s) ===")
    for n in sorted(summary.keys()):
        r = summary[n]
        oeis = A000638.get(n)
        flag = "OK" if oeis is None or r["total"] == oeis else "FAIL"
        print(f"  S_{n}: total={r['total']:>10} "
              f"fpf={r['fpf']:>10} "
              f"oeis={oeis if oeis else '?':>10} "
              f"{flag} ({r['elapsed_s']:.1f}s)")


if __name__ == "__main__":
    main()
