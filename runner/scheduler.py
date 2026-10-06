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
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path

from runner.batches import build_dispatch_tasks, rebalance_super_batches
from runner.cache import get_num_transitive_groups, merge_h_to_qs_fragments
from runner.combos import (
    combo_filename,
    combos_for_partition,
    fpf_partitions,
    init_completeness_cache,
    is_complete_combo_file,
    part_dirname,
    read_combo_count_headers,
    save_completeness_cache,
)
from runner.constants import A000638, A005432, A116693, ROOT, TIMING_BASELINE
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
    # Load the per-output-file completeness cache (size+mtime of files already
    # verified complete) so resume/retry-round scans skip re-reading the ~22 GB
    # output tree.  Saved after each scan below; each restart re-reads only the
    # delta since the last scan.
    init_completeness_cache(sn_out)
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

    # L_FPF(m) per m, accumulated as we walk n_min..n_max.  Needed for the
    # binomial-transform L(n) = sum_{m=0..n} C(n,m) * L_FPF(m) reported at
    # each n.  Seed base cases L_FPF(0)=1, L_FPF(1)=0 plus every known
    # A116693 reference term, so partial-range runs (--n-min > 2) still
    # compute a correct L(n) instead of silently dropping the m < n_min
    # terms (the 2026-06-08/09 "L(21)=L_FPF(21)+1 NEW-TERM" bug — values
    # computed in-run still override the seeds below).
    L_FPF = {0: 1, 1: 0}
    L_FPF.update(A116693)
    failures = []   # loud-exit collector: FPF/labelled mismatches, missing combos
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
        failures_at_n_start = len(failures)

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
        # Persist the completeness cache populated by the scan above so a later
        # restart re-reads only combos finished since now, not the whole tree.
        save_completeness_cache()

        # Run batched bootstrap.  Bootstrap combos are invisible to the retry
        # loop below (route=="bootstrap" is skipped there), so verify the
        # outputs HERE: retry the missing entries once, then abort loudly —
        # every other combo of this n depends on these single-block sources,
        # so continuing would just manufacture a silent undercount at
        # frontier n (2026-06-09 review item).
        n_dispatch_t0 = time.time()
        if bootstrap_entries:
            print(f"[n={n}] bootstrapping {len(bootstrap_entries)} single-block combos...")
            t0 = time.time()
            # Retry with backoff: a machine-load transient (cygwin bash fork
            # failure under a saturated box -> rc=1, empty log+stderr,
            # observed 2026-07-02) fails an immediate retry the same way;
            # waiting out the spike is what actually recovers.
            try:
                bs_attempts = max(1, int(os.environ.get(
                    "BUILD_SN_BOOTSTRAP_RETRIES", "3")))
            except ValueError:
                bs_attempts = 3
            bs_missing = bootstrap_entries
            for attempt in range(bs_attempts):
                if attempt > 0:
                    backoff = 30 * attempt
                    print(f"[n={n}] bootstrap left {len(bs_missing)} combos "
                          f"missing/incomplete - retry {attempt}/"
                          f"{bs_attempts - 1} after {backoff}s backoff")
                    time.sleep(backoff)
                run_bootstrap_batch(
                    bs_missing,
                    pred_tmp / (f"bootstrap_n{n}" if attempt == 0
                                else f"bootstrap_n{n}_retry{attempt}"))
                bs_missing = [e for e in bs_missing
                              if not (e[2].exists() and is_complete_combo_file(e[2]))]
                if not bs_missing:
                    break
            if bs_missing:
                raise RuntimeError(
                    f"[n={n}] bootstrap failed for {len(bs_missing)} single-block "
                    f"combos after {bs_attempts} attempts (first: degree "
                    f"{bs_missing[0][0]}, T-index {bs_missing[0][1]}); see "
                    f"{pred_tmp / f'bootstrap_n{n}_retry{bs_attempts - 1}' / 'bootstrap_0.log'}")
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
            save_completeness_cache()  # persist files newly verified by the dispatch scan

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
                  f"b_power={summary_counts['b_power']}, "
                  f"c2_glue={summary_counts['c2_glue']}, "
                  f"c2_glue2={summary_counts['c2_glue2']}, "
                  f"c3_glue={summary_counts.get('c3_glue', 0)}, "
                  f"identity={summary_counts.get('identity', 0)}, "
                  f"burnside_m2={summary_counts['burnside_m2']}, "
                  f"wreath_ra={summary_counts['wreath_ra']}, "
                  f"wreath_via_2f={summary_counts['wreath_via_2f']}, "
                  f"heavy_left={summary_counts['heavy_left']} "
                  f"@>{args.left_heavy_threshold} classes) on {args.workers} workers")

            n_done = 0
            n_tasks = len(tasks)

            # Memory governor REMOVED 2026-06-11 (user decision): it predated
            # the gens-streaming / windowed-framed-cache / lazy-LEFT-recon /
            # c2_glue memory fixes, which eliminated the 30 GB pair-loop
            # workers it was guarding against — and it gated by predicted
            # CANDIDATE COUNT regardless of route, serializing analytic
            # (b_power/bd8) and streaming (c2_glue) monsters that are cheap
            # on memory by construction.  Plain FIFO over `tasks` now.
            def _handle(fut, kind, key):
                nonlocal n_done, n_gap_wall, n_combos, n_fpf, n_seconds
                try:
                    result = fut.result()
                except Exception as e:
                    print(f"  [n={n}] EXCEPTION ({kind}) {key}: {e}")
                    return
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
                        return
                    n_fpf += result.get("predicted", 0)
                    n_seconds += result.get("elapsed_s", 0)
                    per_combo_results.append({"n": n, "kind": kind,
                                               "key": key, **result})
                if n_done % 25 == 0:
                    print(f"  [n={n}] {n_done}/{n_tasks} tasks done "
                          f"(elapsed={time.time()-n_dispatch_t0:.0f}s)")

            in_flight = {}          # future -> (kind, key)
            task_q = list(tasks)
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                def _fill():
                    while len(in_flight) < args.workers and task_q:
                        kind, key, cmd, timeout = task_q.pop(0)
                        fut = pool.submit(_run_subprocess_task, kind, key, cmd, timeout)
                        in_flight[fut] = (kind, key)

                _fill()
                while in_flight:
                    done, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
                    for fut in done:
                        kind, key = in_flight.pop(fut)
                        _handle(fut, kind, key)
                    _fill()
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
                failures.append(f"n={n}: {final_missing} combos missing after retry exhaustion")

        # Source-of-truth count: read the output tree after all retries.
        # Also harvest the per-combo `# class_sum:` (labelled-subgroup
        # contribution) when present.  Bucketed per partition so we can emit
        # both the FPF count (A000638-style) and L_FPF(n) (A116693-style).
        #
        # For paths not yet inline-instrumented (c2_fast / b_* / wreath_*),
        # invoke labelled_postpass.py for this n to populate sidecars before
        # the scan, then fall back to reading sidecars when the combo file
        # lacks `# class_sum:`.
        postpass_cmd = [
            sys.executable, "-u",
            str(ROOT / "labelled_postpass.py"),
            "--m-min", str(n), "--m-max", str(n),
            "--workers", str(args.workers),
        ]
        # No timeout: large-n combos can take many hours with fallback
        # Normalizer(W,H) on uninstrumented engines.  A finite timeout drops
        # the missing-cs combos to 0, silently undercounting L_FPF(n).  Better
        # to wait; the dispatch already validated the conjugacy class count.
        try:
            subprocess.run(postpass_cmd, cwd=str(ROOT),
                           check=False,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           env={**os.environ, "PREDICT_SN_DIR": str(sn_out)})
        except Exception as e:
            print(f"[n={n}] labelled_postpass error: {e}; aggregation may be incomplete")
        cs_dir = sn_out / "_labelled_cs" / str(n)

        n_combos = 0
        n_fpf = 0
        n_class_sum = 0
        labelled_by_partition = {}
        for partition in partitions:
            part_dir = n_dir / part_dirname(partition)
            part_class_sum = 0
            for combo in combos_for_partition(partition, num_transitive):
                output_path = part_dir / f"{combo_filename(combo)}.g"
                if output_path.exists() and is_complete_combo_file(output_path):
                    # Header-only read (O(1) memory): never slurps a multi-GB
                    # monster body just to grab # deduped / # class_sum.
                    deduped_v, cs_v = read_combo_count_headers(output_path)
                    n_combos += 1
                    n_fpf += deduped_v if deduped_v is not None else 0
                    if cs_v is not None:
                        part_class_sum += cs_v
                    else:
                        # fall back to labelled_postpass sidecar.
                        sc = cs_dir / part_dirname(partition) / f"{combo_filename(combo)}.cs"
                        if sc.exists():
                            sc_text = sc.read_text(encoding="utf-8")
                            mcsc = re.search(r"^# class_sum:\s*(\d+)",
                                             sc_text, re.MULTILINE)
                            if mcsc:
                                part_class_sum += int(mcsc.group(1))
            n_class_sum += part_class_sum
            if part_class_sum:
                labelled_by_partition[part_dirname(partition)] = part_class_sum

        # Compute total subgroups for n: FPF(n) + inherited from S_(n-1).
        wall_s = time.time() - n_dispatch_t0
        if n in A000638 and n - 1 in A000638:
            expected_fpf = A000638[n] - A000638[n - 1]
            ok_fpf = (n_fpf == expected_fpf)
            print(f"[n={n}] CONJ classes  FPF(n)={n_fpf}  expected={expected_fpf}  "
                  f"{'OK' if ok_fpf else 'MISMATCH'}  "
                  f"(gap_cpu={n_seconds:.1f}s gap_wall={n_gap_wall:.1f}s "
                  f"wall={wall_s:.1f}s, {n_combos} combos)")
        else:
            ok_fpf = None
            print(f"[n={n}] CONJ classes  FPF(n)={n_fpf}  (no OEIS reference)  "
                  f"(gap_cpu={n_seconds:.1f}s gap_wall={n_gap_wall:.1f}s "
                  f"wall={wall_s:.1f}s, {n_combos} combos)")

        # --- LABELLED subgroup totals (harvest, A005432 series) --------------
        # n_class_sum is L_FPF(n) for this n; record and binomial-transform to
        # get L(n) = total labelled subgroups of S_n.
        L_FPF[n] = n_class_sum
        if n in A116693:
            fpf_label = "OK" if n_class_sum == A116693[n] else f"MISMATCH(A116693={A116693[n]})"
        else:
            fpf_label = "NEW"
        # L(n) is only meaningful when EVERY L_FPF(m), m <= n, is known
        # (computed this run or seeded from A116693).  On a partial-range run
        # past the seeded terms, report SKIPPED instead of recording a wrong
        # partial sum as a NEW-TERM (fired 2026-06-08 and again 06-09).
        missing_m = [m for m in range(2, n) if m not in L_FPF]
        if missing_m:
            L_n = None
            L_label = (f"SKIPPED(partial-range run: L_FPF unknown for "
                       f"m={missing_m[0]}..{missing_m[-1]})")
        else:
            L_n = sum(math.comb(n, m) * L_FPF[m] for m in range(n + 1))
            if n in A005432:
                L_label = "OK" if L_n == A005432[n] else f"MISMATCH(A005432={A005432[n]})"
            else:
                L_label = "NEW-TERM"
        print(f"[n={n}] LABELLED      L_FPF(n)={n_class_sum} {fpf_label}  "
              f"L(n)={L_n} {L_label}")
        if ok_fpf is False:
            failures.append(f"n={n}: FPF mismatch")
        if "MISMATCH" in fpf_label:
            failures.append(f"n={n}: labelled L_FPF mismatch")
        if "MISMATCH" in L_label:
            failures.append(f"n={n}: labelled L(n) mismatch")

        # --- Timing baseline comparison --------------------------------------
        baseline = TIMING_BASELINE.get(n)
        if baseline is not None:
            ratio = wall_s / baseline
            print(f"[n={n}] timing        {wall_s:.1f}s   baseline {baseline:.1f}s   "
                  f"({ratio:.2f}x baseline)")

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
            "labelled_L_FPF": n_class_sum,                 # L_FPF(n)
            "labelled_L_n": L_n,                           # L(n) = labelled subgroup total
            "labelled_expected_L_FPF": A116693.get(n),
            "labelled_expected_L_n": A005432.get(n),
            "labelled_by_partition": labelled_by_partition,
            "timing_baseline_s": TIMING_BASELINE.get(n),
        }

        # Per-n fail-fast (2026-07-02 audit open item): a bad n must not keep
        # feeding higher-n glue/identity/2-factor runs with corrupt sources
        # for days.  Any count failure recorded at THIS n (retry exhaustion,
        # FPF mismatch, labelled L_FPF/L(n) mismatch vs a known reference)
        # aborts the run now; the summary and failure list are still written.
        # Frontier n (no OEIS/A116693 reference) records nothing here, so a
        # first computation can never false-trigger.  Escape hatch:
        # BUILD_SN_FAILFAST=0 restores the old collect-and-continue.
        new_failures = failures[failures_at_n_start:]
        if new_failures and os.environ.get("BUILD_SN_FAILFAST") != "0":
            summary["failures"] = failures
            (sn_out / "_build_summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8")
            print(f"[n={n}] FAIL-FAST: aborting the run - this n's outputs "
                  f"feed every higher n as sources.  "
                  f"(BUILD_SN_FAILFAST=0 to collect-and-continue.)")
            for f_msg in new_failures:
                print(f"  - {f_msg}")
            sys.exit(1)

    summary["failures"] = failures
    (sn_out / "_build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary written to {sn_out / '_build_summary.json'}")
    # Loud exit on any count mismatch or unconverged n (2026-06-09 review
    # item: MISMATCH/retry-exhaustion used to exit 0, so a wrapping script —
    # or a multi-day frontier run — could sail past a silent failure).
    if failures:
        print("BUILD FAILURES:")
        for f_msg in failures:
            print(f"  - {f_msg}")
        sys.exit(1)
