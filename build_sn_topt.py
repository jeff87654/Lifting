#!/usr/bin/env python3
"""
build_sn_v2.py — Regenerate FPF subgroup data S_2..S_N using the unified
predictors (predict_2factor_topt.py, predict_full_general_wreath.py) plus the
legacy C_2^n linear-algebra fast path.  Output goes to parallel_sn_topt/<n>/
<part>/<combo>.g in the same format as the legacy parallel_sn/.

Routing per combo c (with partition λ = sorted desc {d : (d,t) in c}):
  - len(c) == 1  -> bootstrap (write GeneratorsOfGroup(TransitiveGroup(d,t)))
  - λ has ≥2 trailing 2s -> try C_2 fast path; fall through on `fail`
  - distinguished species (mult=1) -> predict_2factor --mode distinguished
  - ≥2 distinct species clusters -> predict_2factor --mode holt_split
  - m=2 single-cluster -> predict_2factor --mode burnside_m2
  - m≥3 single-cluster -> predict_full_general_wreath
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

# OEIS A000638 (number of subgroups of S_n up to conjugacy).  Used to validate
# total per-n count via FPF(n) = A000638(n) - A000638(n-1).
A000638 = {
    0: 1, 1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96,
    8: 296, 9: 554, 10: 1593, 11: 3094, 12: 10723, 13: 20832,
    14: 75154, 15: 159129, 16: 686165, 17: 1466358, 18: 7274651,
}


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def fpf_partitions(n):
    """All partitions of n into parts >= 2, sorted descending."""
    def gen(remaining, max_part, prefix):
        if remaining == 0:
            yield prefix
            return
        for p in range(min(remaining, max_part), 1, -1):
            yield from gen(remaining - p, p, prefix + [p])
    return list(gen(n, n, []))


def combos_for_partition(partition, num_transitive):
    """Enumerate combos = list of (d, t) tuples.  For repeated d's, t's are
    sorted ascending so each S_n-equivalence class is enumerated exactly once.

    `num_transitive` is a dict {d: NrTransitiveGroups(d)}."""
    # Group by degree
    by_d = {}
    for d in partition:
        by_d[d] = by_d.get(d, 0) + 1
    degrees = sorted(by_d.keys())

    # For each distinct degree d with multiplicity m, choose a multiset of size m
    # from {1..num_transitive[d]} (with repetition, sorted ascending).
    def multisets(items, k):
        if k == 0:
            yield ()
            return
        for i, x in enumerate(items):
            for rest in multisets(items[i:], k - 1):
                yield (x,) + rest

    def cartesian(degs):
        if not degs:
            yield []
            return
        d = degs[0]
        rest = degs[1:]
        for ts in multisets(list(range(1, num_transitive[d] + 1)), by_d[d]):
            for tail in cartesian(rest):
                yield [(d, t) for t in ts] + tail

    for combo in cartesian(degrees):
        yield tuple(sorted(combo))


def combo_filename(combo):
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def part_dirname(partition):
    return "[" + ",".join(str(d) for d in partition) + "]"


def trailing_twos(partition):
    n = 0
    for d in reversed(partition):
        if d == 2:
            n += 1
        else:
            break
    return n


def left_class_count(left_combo, m_left, sn_dir):
    """Read the # deduped: header from the LEFT source file to gate
    super-batching.  Returns the class count, or 0 if source is missing
    (which routes the LEFT to standalone-batch as a safe default)."""
    parts = sorted([d for d, _ in left_combo], reverse=True)
    part_str = "[" + ",".join(str(p) for p in parts) + "]"
    src = Path(sn_dir) / str(m_left) / part_str / f"{combo_filename(left_combo)}.g"
    try:
        with open(src, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^# deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
                if line.startswith("["):
                    break  # no header found before generators
    except OSError:
        pass
    return 0


def is_complete_combo_file(path):
    """Verify a combo .g file is complete: # deduped: N matches the count of
    generator lines.  Returns True if valid, False if missing/truncated/inconsistent.
    Used by resume-skip to detect partial files left by killed mid-write GAP runs."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError):
        return False
    # Strip GAP line-continuation characters ("\<newline>") so generator lines
    # that wrap across multiple physical lines count as one.
    joined = re.sub(r"\\\r?\n", "", text)
    m = re.search(r"^# deduped:\s*(\d+)\s*$", joined, re.MULTILINE)
    if not m:
        return False
    expected = int(m.group(1))
    actual = sum(1 for ln in joined.splitlines() if ln.startswith("["))
    return actual == expected


def route(combo):
    """Return route name string."""
    if len(combo) == 1:
        return "bootstrap"
    partition = sorted([d for d, _ in combo], reverse=True)
    # C_2 fast path is intended for pure C_2^n only (= partition is all 2's).
    # Mixed combos with non-2 prefix go through the regular routes.
    if len(partition) >= 2 and all(d == 2 for d in partition):
        return "c2_fast"
    clusters = Counter(combo)
    if any(mult == 1 for mult in clusters.values()):
        return "distinguished"
    if len(clusters) >= 2:
        return "holt_split"
    sp, mult = next(iter(clusters.items()))
    if mult == 2:
        return "burnside_m2"
    return "wreath_ra"


# ---- Bootstrap (single-block combos) ----

BOOTSTRAP_TEMPLATE = r"""
LogTo("__LOG__");
batch := __BATCH__;
for entry in batch do
    d := entry[1];
    t := entry[2];
    output := entry[3];
    T := TransitiveGroup(d, t);
    gens := GeneratorsOfGroup(T);
    PrintTo(output, "# combo: [ [ ", d, ", ", t, " ] ]\n");
    AppendTo(output, "# candidates: 1\n# deduped: 1\n# elapsed_ms: 0\n");
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    AppendTo(output, "[", s, "]\n");
    Print("BOOTSTRAP_OK d=", d, " t=", t, " path=", output, "\n");
od;
LogTo();
QUIT;
"""


def run_bootstrap_batch(entries, tmp_dir):
    """Bootstrap multiple single-block combos in one GAP session.
    `entries` = list of (d, t, output_path)."""
    if not entries:
        return
    tmp_dir.mkdir(parents=True, exist_ok=True)
    log = tmp_dir / "bootstrap.log"
    if log.exists(): log.unlink()
    batch_str = "[" + ",".join(
        f'[{d},{t},"{to_cyg(p)}"]' for d, t, p in entries) + "]"
    run_g = tmp_dir / "bootstrap_run.g"
    run_g.write_text(
        BOOTSTRAP_TEMPLATE
        .replace("__LOG__", to_cyg(log))
        .replace("__BATCH__", batch_str),
        encoding="utf-8"
    )
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)


# ---- Run a non-bootstrap combo ----

def run_predictor(predictor_script, combo_str, output_path, extra_args=None,
                  timeout=3600):
    """Invoke a predictor as a subprocess and return its result dict."""
    args = [sys.executable, str(ROOT / predictor_script),
            "--combo", combo_str,
            "--output-path", str(output_path)]
    if extra_args:
        args.extend(extra_args)
    args.extend(["--timeout", str(timeout)])
    t0 = time.time()
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                               timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"error": "wrapper timeout", "elapsed_s": time.time() - t0}
    if proc.returncode != 0:
        return {"error": f"predictor rc={proc.returncode}",
                "stderr": proc.stderr[-500:],
                "stdout": proc.stdout[-500:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "json parse",
                "stdout": proc.stdout[-500:]}


def run_combo(n, partition, combo, output_path, log_path, force=False,
              timeout=3600):
    """Generate one combo's file at output_path.  Returns dict with keys:
    {route, count, elapsed_s, [error]}."""
    if output_path.exists() and not force:
        # Re-read deduped count from existing file.
        text = output_path.read_text(encoding="utf-8")
        m = re.search(r"^# deduped:\s*(\d+)", text, re.MULTILINE)
        return {"route": "skipped", "count": int(m.group(1)) if m else 0,
                "elapsed_s": 0.0}

    route_name = route(combo)
    combo_str = combo_filename(combo)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if route_name == "bootstrap":
        # caller batches these separately
        return {"route": "bootstrap", "count": 1, "elapsed_s": 0.0,
                "deferred": True}

    # Try C_2 fast path first if eligible.
    if route_name == "c2_fast":
        result = run_predictor("run_c2_fast_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": "c2_fast", "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Fall through to other routes if C_2 path rejected.
        clusters = Counter(combo)
        if any(mult == 1 for mult in clusters.values()):
            route_name = "distinguished"
        elif len(clusters) >= 2:
            route_name = "holt_split"
        elif clusters[next(iter(clusters))] == 2:
            route_name = "burnside_m2"
        else:
            route_name = "wreath_ra"

    if route_name in ("distinguished", "holt_split", "burnside_m2"):
        result = run_predictor("predict_2factor_topt.py", combo_str, output_path,
                                extra_args=["--mode", route_name, "--force"],
                                timeout=timeout)
        if "error" in result:
            return {"route": route_name, "error": result, "count": 0,
                    "elapsed_s": result.get("elapsed_s", 0)}
        return {"route": route_name, "count": result["predicted"],
                "elapsed_s": result["elapsed_s"]}

    if route_name == "wreath_ra":
        result = run_predictor("predict_full_general_wreath.py", combo_str,
                                output_path,
                                extra_args=["--target-n", str(n)],
                                timeout=timeout)
        if "error" in result:
            return {"route": route_name, "error": result, "count": 0,
                    "elapsed_s": result.get("elapsed_s", 0)}
        return {"route": route_name, "count": result["predicted"],
                "elapsed_s": result["elapsed_s"]}

    return {"route": route_name, "error": "unhandled route", "count": 0,
            "elapsed_s": 0}


# ---- Subprocess task runner (called by ProcessPoolExecutor) ----
def _run_subprocess_task(kind, key, cmd, timeout):
    """Run one task as a subprocess.  Returns dict with kind/key plus
    parsed JSON output (if available).  timeout=None means run indefinitely."""
    t0 = time.time()
    try:
        if timeout is None:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"kind": kind, "key": key, "error": "timeout",
                "elapsed_s": time.time() - t0}
    if proc.returncode != 0:
        return {"kind": kind, "key": key,
                "error": f"rc={proc.returncode}",
                "stderr": proc.stderr[-500:],
                "stdout": proc.stdout[-500:],
                "elapsed_s": time.time() - t0}
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"kind": kind, "key": key, "error": "json parse",
                "stdout": proc.stdout[-500:], "stderr": proc.stderr[-500:],
                "elapsed_s": time.time() - t0}
    if kind in ("batch", "super_batch"):
        return {"kind": kind, "key": key, "results": parsed,
                "elapsed_s": time.time() - t0}
    return {"kind": kind, "key": key, "elapsed_s": time.time() - t0,
            **(parsed if isinstance(parsed, dict) else {"raw": parsed})}


# ---- Main loop ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, default=2)
    ap.add_argument("--n-max", type=int, default=18)
    ap.add_argument("--out", default=str(ROOT / "parallel_sn_topt"),
                    help="output root (parallel_sn_topt/)")
    ap.add_argument("--h-cache", default=str(ROOT / "predict_species_tmp" / "_h_cache_topt"),
                    help="fresh H-cache directory")
    ap.add_argument("--predictor-tmp",
                    default=str(ROOT / "predict_species_tmp" / "_two_factor_topt"),
                    help="predictor temp work dir")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing combo files")
    ap.add_argument("--combo-timeout", type=int, default=0,
                    help="per-combo timeout in seconds; 0 means no timeout (default)")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel workers for batch/c2/wreath dispatch (default 1)")
    ap.add_argument("--super-batch-jobs", type=int, default=1,
                    help="if >1, pack small batch-groups into super-batches with this many "
                         "total jobs each (default 1 = no super-batching)")
    ap.add_argument("--left-heavy-threshold", type=int, default=1000,
                    help="LEFT sources with > this many deduped classes always run as their "
                         "own standalone batch (one fresh GAP per heavy LEFT) regardless of "
                         "super-batching, to avoid GAP runtime degradation on long jobs")
    args = ap.parse_args()

    sn_out = Path(args.out)
    sn_out.mkdir(parents=True, exist_ok=True)
    h_cache = Path(args.h_cache)
    h_cache.mkdir(parents=True, exist_ok=True)
    pred_tmp = Path(args.predictor_tmp)
    pred_tmp.mkdir(parents=True, exist_ok=True)

    # Set env vars so predictors read sources from sn_out and write h_cache to fresh dir.
    os.environ["PREDICT_SN_DIR"] = str(sn_out)
    os.environ["PREDICT_H_CACHE_DIR"] = str(h_cache)
    os.environ["PREDICT_TMP_DIR"] = str(pred_tmp)

    # Get NrTransitiveGroups via one GAP call upfront.
    num_transitive = get_num_transitive_groups(args.n_max, sn_out)

    summary = {"per_n": {}, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    for n in range(args.n_min, args.n_max + 1):
        # Reverse partition order: smaller first-part partitions like
        # [4,4,4,2,2] are typically heavier (more combos, more complex
        # cluster structure) than [n] or [n-2, 2].  Dispatching heavier
        # partitions first lets the worker pool drain the long tail early,
        # so workers stay busy instead of idling at the end on a slow task.
        partitions = list(reversed(fpf_partitions(n)))
        n_combos = 0
        n_fpf = 0
        n_seconds = 0.0
        n_dir = sn_out / str(n)
        n_dir.mkdir(exist_ok=True)
        bootstrap_entries = []
        per_combo_results = []

        # Pre-collect bootstrap entries for batching.
        n_invalid_skipped = 0
        for partition in partitions:
            part_dir = n_dir / part_dirname(partition)
            part_dir.mkdir(exist_ok=True)
            for combo in combos_for_partition(partition, num_transitive):
                output_path = part_dir / f"{combo_filename(combo)}.g"
                if output_path.exists() and not args.force:
                    if is_complete_combo_file(output_path):
                        continue
                    # Truncated/inconsistent file: delete and re-attempt.
                    n_invalid_skipped += 1
                    output_path.unlink()
                if route(combo) == "bootstrap":
                    d, t = combo[0]
                    bootstrap_entries.append((d, t, output_path))
        if n_invalid_skipped > 0:
            print(f"[n={n}] purged {n_invalid_skipped} invalid/truncated combo files; will recompute")

        # Run batched bootstrap.
        n_dispatch_t0 = time.time()
        if bootstrap_entries:
            print(f"[n={n}] bootstrapping {len(bootstrap_entries)} single-block combos...")
            t0 = time.time()
            run_bootstrap_batch(bootstrap_entries, pred_tmp / f"bootstrap_n{n}")
            print(f"  bootstrap done in {time.time()-t0:.1f}s")

        # Group non-bootstrap, non-c2_fast combos by LEFT source path so
        # predict_2factor_topt.py can batch them in a single GAP session.  C_2 fast
        # path and Wreath-RA combos remain per-combo.
        # Group key: (mode_for_predict_2factor, left_combo_tuple)
        from predict_2factor_topt import resolve_inputs as _resolve_inputs
        batch_groups = {}     # (left_combo) -> list of (combo, mode, output_path, partition)
        left_m_for_combo = {} # left_combo -> m_left (for heavy-LEFT detection)
        c2_combos = []        # list of (combo, output_path, partition)
        wreath_combos = []    # list of (combo, output_path, partition)

        for partition in partitions:
            part_dir = n_dir / part_dirname(partition)
            for combo in combos_for_partition(partition, num_transitive):
                output_path = part_dir / f"{combo_filename(combo)}.g"
                if output_path.exists() and not args.force:
                    if is_complete_combo_file(output_path):
                        continue
                    output_path.unlink()   # truncated; will be recomputed
                rt = route(combo)
                if rt == "bootstrap":
                    continue   # already done above
                if rt == "c2_fast":
                    c2_combos.append((combo, output_path, partition))
                    continue
                if rt == "wreath_ra":
                    wreath_combos.append((combo, output_path, partition))
                    continue
                # 2-factor route: distinguished, holt_split, or burnside_m2
                try:
                    inputs = _resolve_inputs(combo, rt)
                except Exception as e:
                    print(f"  [n={n}] resolve_inputs failed for {combo_filename(combo)}: {e}")
                    continue
                key = inputs["left_combo"]
                batch_groups.setdefault(key, []).append((combo, rt, output_path, partition))
                left_m_for_combo[key] = inputs["m_left"]

        # ---- Build task list (parallelizable) ----
        tasks = []   # list of (kind, key_for_msg, cmd, timeout)

        # 2-factor batch tasks.  When --super-batch-jobs > 1, pack small batch
        # groups into super-batches that share GAP startup.  Big groups (with
        # >= super_batch_jobs/2 jobs each) stay as standalone batches since
        # they already amortize startup well.
        sb_jobs = args.super_batch_jobs
        sb_threshold = max(1, sb_jobs // 2)
        # Group count cap: only the job-count cap (sb_jobs) is enforced.
        # Previously capped at args.workers, which artificially limited
        # amortization of GAP startup.

        super_pack_groups = []
        super_pack_total_jobs = 0
        super_pack_idx = 0

        def flush_super_pack():
            nonlocal super_pack_groups, super_pack_total_jobs, super_pack_idx
            if not super_pack_groups: return
            sb_dir = pred_tmp / f"super_n{n}_sp{super_pack_idx}"
            sb_dir.mkdir(parents=True, exist_ok=True)
            sb_json = sb_dir / "super.json"
            sb_json.write_text(json.dumps({
                "groups": [
                    {"left_combo": list(lc),
                     "jobs": [{"combo": list(c), "mode": m, "output_path": str(o)}
                              for (c, m, o, _) in jobs]}
                    for lc, jobs in super_pack_groups
                ]
            }), encoding="utf-8")
            if args.combo_timeout == 0:
                inner_timeout = 0   # 0 = no timeout
                outer_timeout = None
            else:
                inner_timeout = args.combo_timeout * super_pack_total_jobs + 120
                outer_timeout = args.combo_timeout * super_pack_total_jobs + 240
            cmd = [sys.executable, "predict_2factor_topt.py",
                   "--super-batch", str(sb_json), "--force",
                   "--timeout", str(inner_timeout)]
            label = f"super_{super_pack_idx}({len(super_pack_groups)}grp,{super_pack_total_jobs}j)"
            tasks.append(("super_batch", label, cmd, outer_timeout))
            super_pack_idx += 1
            super_pack_groups = []
            super_pack_total_jobs = 0

        n_heavy_routed = 0
        for left_combo, group_jobs in batch_groups.items():
            n_jobs = len(group_jobs)
            # Heavy LEFT (large class count) always gets standalone batch:
            # GAP runtime degradation makes long-lived workers ~25x slower per
            # fp after even 30 min, so each heavy LEFT deserves a fresh GAP.
            m_left = left_m_for_combo.get(left_combo)
            lsize = left_class_count(left_combo, m_left, sn_out) if m_left else 0
            heavy = lsize > args.left_heavy_threshold
            if heavy:
                n_heavy_routed += 1
            if not heavy and sb_jobs > 1 and n_jobs <= sb_threshold:
                # Pack into super-batch.
                super_pack_groups.append((left_combo, group_jobs))
                super_pack_total_jobs += n_jobs
                # Flush when the job count cap is reached.
                if super_pack_total_jobs >= sb_jobs:
                    flush_super_pack()
                continue
            # Heavy LEFT, big group, or no super-batching: standalone batch.
            batch_dir = pred_tmp / f"batch_n{n}_{combo_filename(left_combo)}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            jobs_json = batch_dir / "jobs.json"
            jobs_json.write_text(json.dumps([
                {"combo": list(combo), "mode": mode,
                 "output_path": str(out)}
                for combo, mode, out, _ in group_jobs
            ]), encoding="utf-8")
            if args.combo_timeout == 0:
                inner_timeout = 0   # 0 = no timeout
                outer_timeout = None
            else:
                inner_timeout = args.combo_timeout * n_jobs
                outer_timeout = args.combo_timeout * n_jobs + 120
            cmd = [sys.executable, "predict_2factor_topt.py",
                   "--batch", str(jobs_json), "--force",
                   "--timeout", str(inner_timeout)]
            tasks.append(("batch", combo_filename(left_combo), cmd, outer_timeout))
        flush_super_pack()

        if args.combo_timeout == 0:
            single_inner_timeout = 0   # 0 = no timeout
            single_outer_timeout = None
        else:
            single_inner_timeout = args.combo_timeout
            single_outer_timeout = args.combo_timeout + 60

        # C_2 fast tasks: one per combo.
        for combo, output_path, partition in c2_combos:
            cmd = [sys.executable, "run_c2_fast_path.py",
                   "--combo", combo_filename(combo),
                   "--output-path", str(output_path),
                   "--timeout", str(single_inner_timeout)]
            tasks.append(("c2", combo_filename(combo), cmd, single_outer_timeout))

        # Wreath-RA tasks: one per combo.
        for combo, output_path, partition in wreath_combos:
            cmd = [sys.executable, "predict_full_general_wreath.py",
                   "--combo", combo_filename(combo),
                   "--target-n", str(n),
                   "--output-path", str(output_path),
                   "--timeout", str(single_inner_timeout)]
            tasks.append(("wreath", combo_filename(combo), cmd, single_outer_timeout))

        # Reorder: dispatch wreath tasks first (each is single-threaded
        # GAP work that can take 30+ minutes — the long tail).  Then c2,
        # then 2-factor batches.  Stable sort preserves intra-kind order.
        tasks.sort(key=lambda t: {"wreath": 0, "c2": 1,
                                   "super_batch": 2, "batch": 2}.get(t[0], 3))

        # Late-stage rebalance: if we have fewer tasks than workers, split the
        # largest multi-group super-batches in half until we have enough or
        # all super-batches are singleton-group.  Keeps all workers busy when
        # there are heavy long-tail tasks left.
        def _split_largest_super_batch():
            """Pop the super-batch with the most groups; split it in half;
            re-add as two new super_batch tasks.  Returns True if split."""
            sb_indices = [i for i, t in enumerate(tasks) if t[0] == "super_batch"]
            if not sb_indices:
                return False
            # Find sb with most groups.
            def n_groups(i):
                # Reread the sb_json file — cmd holds the path.
                cmd = tasks[i][2]
                sb_json_path = cmd[cmd.index("--super-batch") + 1]
                try:
                    return len(json.loads(Path(sb_json_path).read_text())["groups"])
                except Exception:
                    return 0
            sb_indices.sort(key=lambda i: -n_groups(i))
            target = sb_indices[0]
            cmd = tasks[target][2]
            sb_json_path = cmd[cmd.index("--super-batch") + 1]
            data = json.loads(Path(sb_json_path).read_text())
            groups = data["groups"]
            if len(groups) <= 1:
                return False
            mid = len(groups) // 2
            left_groups, right_groups = groups[:mid], groups[mid:]
            # Write two new sb_json files.
            sb_dir_a = pred_tmp / f"super_n{n}_sp{super_pack_idx}"
            sb_dir_a.mkdir(parents=True, exist_ok=True)
            sb_json_a = sb_dir_a / "super.json"
            sb_json_a.write_text(json.dumps({"groups": left_groups}), encoding="utf-8")
            sb_dir_b = pred_tmp / f"super_n{n}_sp{super_pack_idx + 1}"
            sb_dir_b.mkdir(parents=True, exist_ok=True)
            sb_json_b = sb_dir_b / "super.json"
            sb_json_b.write_text(json.dumps({"groups": right_groups}), encoding="utf-8")
            n_jobs_a = sum(len(g["jobs"]) for g in left_groups)
            n_jobs_b = sum(len(g["jobs"]) for g in right_groups)
            inner_to = 0 if args.combo_timeout == 0 else args.combo_timeout * max(n_jobs_a, n_jobs_b) + 120
            outer_to = None if args.combo_timeout == 0 else args.combo_timeout * max(n_jobs_a, n_jobs_b) + 240
            new_a = ("super_batch",
                     f"super_{super_pack_idx}({len(left_groups)}grp,{n_jobs_a}j,split)",
                     [sys.executable, "predict_2factor_topt.py",
                      "--super-batch", str(sb_json_a), "--force",
                      "--timeout", str(inner_to)],
                     outer_to)
            new_b = ("super_batch",
                     f"super_{super_pack_idx + 1}({len(right_groups)}grp,{n_jobs_b}j,split)",
                     [sys.executable, "predict_2factor_topt.py",
                      "--super-batch", str(sb_json_b), "--force",
                      "--timeout", str(inner_to)],
                     outer_to)
            tasks.pop(target)
            tasks.append(new_a)
            tasks.append(new_b)
            return True

        # Now re-bind super_pack_idx for the rebalance loop.
        # (super_pack_idx grew during the per-LEFT pack loop; bump it to leave
        # room for the new split tasks.)
        rebalance_iters = 0
        while len(tasks) < args.workers and rebalance_iters < args.workers * 4:
            if not _split_largest_super_batch():
                break
            super_pack_idx += 2
            rebalance_iters += 1
        if rebalance_iters > 0:
            print(f"[n={n}] rebalanced: split {rebalance_iters} super-batch(es) "
                  f"to keep all {args.workers} workers busy")

        if not tasks:
            pass  # nothing to do this n
        else:
            print(f"[n={n}] dispatching {len(tasks)} tasks "
                  f"(batches={len(batch_groups)}, c2={len(c2_combos)}, "
                  f"wreath={len(wreath_combos)}, heavy_left={n_heavy_routed} "
                  f"@>{args.left_heavy_threshold} classes) on {args.workers} workers")
            from concurrent.futures import ProcessPoolExecutor, as_completed
            n_done = 0
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(_run_subprocess_task, kind, key, cmd, timeout): (kind, key)
                           for kind, key, cmd, timeout in tasks}
                for f in as_completed(futures):
                    kind, key = futures[f]
                    try:
                        result = f.result()
                    except Exception as e:
                        print(f"  [n={n}] EXCEPTION ({kind}) {key}: {e}")
                        continue
                    n_done += 1
                    if kind in ("batch", "super_batch"):
                        if "error" in result and "results" not in result:
                            err_msg = f"  [n={n}] {kind} OUTER ERROR {key}: {result['error']}"
                            stderr_tail = result.get("stderr", "")
                            stdout_tail = result.get("stdout", "")
                            if stderr_tail:
                                err_msg += f"\n    stderr: {stderr_tail[-300:]!r}"
                            if stdout_tail:
                                err_msg += f"\n    stdout: {stdout_tail[-300:]!r}"
                            print(err_msg)
                        for rj in result.get("results", []):
                            n_combos += 1
                            if "error" in rj:
                                print(f"  [n={n}] {kind} ERROR {key}: {rj['error']}")
                                continue
                            n_fpf += rj.get("predicted", 0)
                            n_seconds += rj.get("elapsed_s", 0)
                            per_combo_results.append({"n": n, **rj})
                    else:
                        # c2 or wreath: single result
                        n_combos += 1
                        if "error" in result:
                            err_msg = f"  [n={n}] {kind} ERROR {key}: {result['error']}"
                            stderr_tail = result.get("stderr", "")
                            stdout_tail = result.get("stdout", "")
                            if stderr_tail:
                                err_msg += f"\n    stderr: {stderr_tail[-300:]!r}"
                            if stdout_tail:
                                err_msg += f"\n    stdout: {stdout_tail[-300:]!r}"
                            print(err_msg)
                            continue
                        n_fpf += result.get("predicted", 0)
                        n_seconds += result.get("elapsed_s", 0)
                        per_combo_results.append({"n": n, "kind": kind,
                                                   "key": key, **result})
                    if n_done % 25 == 0:
                        print(f"  [n={n}] {n_done}/{len(tasks)} tasks done "
                              f"(elapsed={time.time()-n_dispatch_t0:.0f}s)")

        # Re-count bootstrap files (they were skipped from per-combo loop).
        for partition in partitions:
            part_dir = n_dir / part_dirname(partition)
            for combo in combos_for_partition(partition, num_transitive):
                if route(combo) != "bootstrap": continue
                output_path = part_dir / f"{combo_filename(combo)}.g"
                if output_path.exists():
                    m = re.search(r"^# deduped:\s*(\d+)",
                                   output_path.read_text(encoding="utf-8"),
                                   re.MULTILINE)
                    n_combos += 1
                    n_fpf += int(m.group(1)) if m else 0

        # Compute total subgroups for n: FPF(n) + inherited from S_(n-1).
        # Inherited count = A000638(n-1) (every S_(n-1)-class extends).
        wall_s = time.time() - n_dispatch_t0
        if n in A000638 and n - 1 in A000638:
            expected_fpf = A000638[n] - A000638[n - 1]
            ok = (n_fpf == expected_fpf)
            print(f"[n={n}] FPF total: {n_fpf}  expected: {expected_fpf}  "
                  f"{'OK' if ok else 'MISMATCH'}  "
                  f"(gap_cpu={n_seconds:.1f}s wall={wall_s:.1f}s, {n_combos} combos)")
        else:
            print(f"[n={n}] FPF total: {n_fpf}  (no OEIS reference)  "
                  f"(gap_cpu={n_seconds:.1f}s wall={wall_s:.1f}s, {n_combos} combos)")

        # Dump per-task timing for offline analysis
        tasks_path = sn_out / f"_n{n}_tasks.json"
        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump(per_combo_results, f)
        # Print top-10 slowest tasks (combos by elapsed_s)
        slow = sorted(per_combo_results,
                      key=lambda r: r.get("elapsed_s", 0), reverse=True)[:10]
        if slow and slow[0].get("elapsed_s", 0) >= 1.0:
            print(f"  [n={n}] top-10 slowest tasks:")
            for r in slow:
                e = r.get("elapsed_s", 0)
                if e < 0.5: break
                combo = r.get("combo", r.get("key", "?"))
                mode = r.get("mode", r.get("kind", "?"))
                pred = r.get("predicted", "?")
                print(f"    {e:7.2f}s {mode:>16}  predicted={pred}  combo={combo}")
        # Aggregate per route
        by_kind = {}
        for r in per_combo_results:
            k = r.get("kind", r.get("mode", "unknown"))
            by_kind.setdefault(k, [0, 0.0])
            by_kind[k][0] += 1
            by_kind[k][1] += r.get("elapsed_s", 0)
        if by_kind:
            print(f"  [n={n}] by route:  " + "  ".join(
                f"{k}={cnt}/{tot:.1f}s" for k, (cnt, tot) in
                sorted(by_kind.items(), key=lambda x: -x[1][1])))

        summary["per_n"][n] = {
            "fpf_total": n_fpf,
            "n_combos": n_combos,
            "elapsed_s": n_seconds,
            "wall_s": wall_s,
            "expected_fpf": (A000638[n] - A000638[n-1]) if (n in A000638 and n-1 in A000638) else None,
        }

    # Write summary
    (sn_out / "_build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary written to {sn_out / '_build_summary.json'}")


# Helper: cache NrTransitiveGroups via one GAP call.
def get_num_transitive_groups(n_max, work_dir):
    cache_file = work_dir / "_num_transitive.json"
    cached = {}
    if cache_file.exists():
        cached = {int(k): v for k, v in json.loads(cache_file.read_text()).items()}
        # Extend cache if n_max grew since last run.
        if all(d in cached for d in range(1, n_max + 1)):
            return cached
    work_dir.mkdir(parents=True, exist_ok=True)
    log = work_dir / "_num_transitive.log"
    run_g = work_dir / "_num_transitive_run.g"
    run_g.write_text(
        f'LogTo("{to_cyg(log)}");\n'
        f'for d in [1..{n_max}] do\n'
        f'    Print("NRT ", d, " ", NrTransitiveGroups(d), "\\n");\n'
        f'od;\n'
        f'LogTo();\nQUIT;\n', encoding="utf-8"
    )
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    log_text = log.read_text(encoding="utf-8") if log.exists() else ""
    result = {}
    for m in re.finditer(r"NRT\s+(\d+)\s+(\d+)", log_text):
        result[int(m.group(1))] = int(m.group(2))
    cache_file.write_text(json.dumps(result), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
