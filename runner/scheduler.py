"""The per-n orchestrator.

`main()` is the top-level entry point: it parses CLI args, sets up output /
cache / temp directories, then loops `n = n_min..n_max` doing for each `n`:

1. enumerate partitions and combos,
2. pre-bootstrap single-block combos (in one GAP session, batched),
3. retry-loop: build task list via `runner.batches.build_dispatch_tasks`,
   rebalance super-batches, dispatch through `ProcessPoolExecutor`,
4. source-of-truth re-count from the output tree,
5. validate against OEIS A000638,
6. merge h_to_qs fragments into the master catalog,
7. write per-n task timings and a summary.

Performance-critical orderings live in `runner.batches`; this file owns only
the loop structure, the retry policy (`MAX_RETRY_ROUNDS = 3`), the pool
wiring, and the summary / validation reporting.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from runner.batches import build_dispatch_tasks, rebalance_super_batches
from runner.cache import get_num_transitive_groups, merge_h_to_qs_fragments
from runner.combos import (
    combo_filename,
    combos_for_partition,
    fpf_partitions,
    is_complete_combo_file,
    part_dirname,
)
from runner.constants import A000638, ROOT
from runner.predictors import (
    BATCH_KINDS,
    _run_subprocess_task,
    run_bootstrap_batch,
)
from runner.route import route


MAX_RETRY_ROUNDS = 3


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

    sn_out = Path(args.out).resolve()
    sn_out.mkdir(parents=True, exist_ok=True)
    h_cache = Path(args.h_cache).resolve()
    h_cache.mkdir(parents=True, exist_ok=True)
    pred_tmp = Path(args.predictor_tmp).resolve()
    pred_tmp.mkdir(parents=True, exist_ok=True)

    # Set env vars so predictors read sources from sn_out and write h_cache to fresh dir.
    os.environ["PREDICT_SN_DIR"] = str(sn_out)
    os.environ["PREDICT_H_CACHE_DIR"] = str(h_cache)
    os.environ["PREDICT_TMP_DIR"] = str(pred_tmp)

    # Get NrTransitiveGroups via one GAP call upfront.
    num_transitive = get_num_transitive_groups(args.n_max, sn_out)

    # Merge any leftover h_to_qs fragments from prior runs into the master
    # cache before workers start.  Sound across kills/restarts because each
    # fragment is a self-contained sentinel-validated GAP file.
    merge_h_to_qs_fragments(h_cache)

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
        n_gap_wall = 0.0
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

        for retry_round in range(MAX_RETRY_ROUNDS + 1):
            if retry_round > 0:
                # Source-of-truth convergence check.
                missing = 0
                for partition in partitions:
                    part_dir = n_dir / part_dirname(partition)
                    for combo in combos_for_partition(partition, num_transitive):
                        if route(combo) == "bootstrap":
                            continue
                        output_path = part_dir / f"{combo_filename(combo)}.g"
                        if output_path.exists() and is_complete_combo_file(output_path):
                            continue
                        missing += 1
                if missing == 0:
                    print(f"[n={n}] all combos accounted for after retry_round={retry_round - 1}")
                    break
                print(f"[n={n}] retry round {retry_round}/{MAX_RETRY_ROUNDS}: "
                      f"{missing} combos missing output - re-dispatching")

            tasks, summary_counts, super_pack_idx = build_dispatch_tasks(
                args, n, partitions, num_transitive, sn_out, n_dir, pred_tmp,
                retry_round)

            _, rebalance_iters = rebalance_super_batches(
                tasks, args, pred_tmp, n, super_pack_idx)
            if rebalance_iters > 0:
                print(f"[n={n}] rebalanced: split {rebalance_iters} super-batch(es) "
                      f"to keep all {args.workers} workers busy")

            if not tasks:
                continue  # nothing to do this round

            print(f"[n={n}] dispatching {len(tasks)} tasks "
                  f"(batches={summary_counts['batches']}, "
                  f"c2={summary_counts['c2']}, "
                  f"c2_factor={summary_counts['c2_factor']}, "
                  f"bd8={summary_counts['bd8']}, "
                  f"elemab={summary_counts['elemab']}, "
                  f"burnside_m2={summary_counts['burnside_m2']}, "
                  f"wreath_ra={summary_counts['wreath_ra']}, "
                  f"wreath_via_2f={summary_counts['wreath_via_2f']}, "
                  f"heavy_left={summary_counts['heavy_left']} "
                  f"@>{args.left_heavy_threshold} classes) on {args.workers} workers")

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
                    n_gap_wall += result.get("elapsed_s", 0.0)
                    if kind in BATCH_KINDS:
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
        else:
            # Retry loop completed without break: convergence not reached.
            final_missing = 0
            for partition in partitions:
                part_dir = n_dir / part_dirname(partition)
                for combo in combos_for_partition(partition, num_transitive):
                    if route(combo) == "bootstrap":
                        continue
                    output_path = part_dir / f"{combo_filename(combo)}.g"
                    if output_path.exists() and is_complete_combo_file(output_path):
                        continue
                    final_missing += 1
            if final_missing > 0:
                print(f"[n={n}] WARNING: {final_missing} combos still missing "
                      f"after {MAX_RETRY_ROUNDS} retry rounds - re-run the orchestrator to recover")

        # Source-of-truth count: read the output tree after all retries.
        n_combos = 0
        n_fpf = 0
        for partition in partitions:
            part_dir = n_dir / part_dirname(partition)
            for combo in combos_for_partition(partition, num_transitive):
                output_path = part_dir / f"{combo_filename(combo)}.g"
                if output_path.exists() and is_complete_combo_file(output_path):
                    m = re.search(r"^# deduped:\s*(\d+)",
                                   output_path.read_text(encoding="utf-8"),
                                   re.MULTILINE)
                    n_combos += 1
                    n_fpf += int(m.group(1)) if m else 0

        # Compute total subgroups for n: FPF(n) + inherited from S_(n-1).
        wall_s = time.time() - n_dispatch_t0
        if n in A000638 and n - 1 in A000638:
            expected_fpf = A000638[n] - A000638[n - 1]
            ok = (n_fpf == expected_fpf)
            print(f"[n={n}] FPF total: {n_fpf}  expected: {expected_fpf}  "
                  f"{'OK' if ok else 'MISMATCH'}  "
                  f"(gap_cpu={n_seconds:.1f}s gap_wall={n_gap_wall:.1f}s "
                  f"wall={wall_s:.1f}s, {n_combos} combos)")
        else:
            print(f"[n={n}] FPF total: {n_fpf}  (no OEIS reference)  "
                  f"(gap_cpu={n_seconds:.1f}s gap_wall={n_gap_wall:.1f}s "
                  f"wall={wall_s:.1f}s, {n_combos} combos)")

        # Merge h_to_qs fragments emitted by workers during this n into the
        # master cache so subsequent n's start with full coverage.
        merge_h_to_qs_fragments(h_cache)

        # Per-task timings for offline analysis.
        tasks_path = sn_out / f"_n{n}_tasks.json"
        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump(per_combo_results, f)

        slow = sorted(per_combo_results,
                      key=lambda r: r.get("elapsed_s", 0), reverse=True)[:10]
        if slow and slow[0].get("elapsed_s", 0) >= 1.0:
            print(f"  [n={n}] top-10 slowest tasks:")
            for r in slow:
                e = r.get("elapsed_s", 0)
                if e < 0.5:
                    break
                combo = r.get("combo", r.get("key", "?"))
                mode = r.get("mode", r.get("kind", "?"))
                pred = r.get("predicted", "?")
                print(f"    {e:7.2f}s {mode:>16}  predicted={pred}  combo={combo}")

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

    (sn_out / "_build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary written to {sn_out / '_build_summary.json'}")
