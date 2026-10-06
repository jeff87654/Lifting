"""Per-n task list construction.

`build_dispatch_tasks(...)` turns the partitions × combos × routing decisions
into a flat list of `(kind, key, cmd, timeout)` tuples ready to feed to the
`ProcessPoolExecutor`.  It owns:

- per-route classification (c2, c2_factor, burnside_m2, wreath_ra,
  wreath_via_2f, generic 2-factor),
- v2legacy routing (the new code's swap-iso path crashes on certain TG
  groups; v2legacy handles them),
- super-batch packing for small 2-factor groups (shares one GAP session for
  many small LEFTs to amortize startup cost),
- heavy-LEFT detection (LEFTs with > `--left-heavy-threshold` classes get
  their own standalone batch since GAP runtime degradation makes long-lived
  workers slow per-fp),
- task-kind priority ordering (wreath first as the long tail, then c2,
  then batches).

`rebalance_super_batches(...)` is the late-stage split that keeps all
workers busy when the task count drops below the worker count.

This module owns several performance-critical heuristics: do not change the
thresholds, the ordering, or the heavy-LEFT routing without re-benchmarking
the S2..S16 8-worker run.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

from runner.combos import (
    combo_filename,
    combos_for_partition,
    is_complete_combo_file,
    left_class_count,
    part_dirname,
)
from runner.predictors import (
    TASK_KIND_BATCH,
    TASK_KIND_BD8,
    TASK_KIND_B_POWER,
    TASK_KIND_C2,
    TASK_KIND_C2_FACTOR_BATCH,
    TASK_KIND_C2_GLUE_BATCH,
    TASK_KIND_C2_GLUE2_BATCH,
    TASK_KIND_C2_GLUE2_SHARDED,
    TASK_KIND_ELEMAB,
    TASK_KIND_IDENTITY_BATCH,
    TASK_KIND_SUPER_BATCH,
    TASK_KIND_WREATH,
    TASK_KIND_WREATH_VIA_2F,
)
from runner.route import route


def _routes_to_v2(left_combo, j):
    """Heuristic: send this 2-factor job to predict_2factor_topt_v2legacy.py
    instead of predict_2factor_topt.py.  v2legacy uses the simpler
    InverseGeneralMapping-based swap detection which works for groups where
    the new code's type-incorrect GAP `*` composition crashes (TG(8,9),
    TG(8,11), etc.) or where qfree3/H_CACHE misfires on complex RIGHT
    clusters (observed 360x regressions on e.g. [2,1]_[2,1]_[6,13]_[6,13]).

    Route to v2legacy when any of:
      (a) LEFT cluster is 1-part (distinguished 2-part combos);
      (b) the FULL partition contains a part >= 9 (e.g. [12,2,2] at n=16);
      (c) the job's mode is "holt_split".

    All-small-partition multi-cluster combos go to v3 even when these would
    otherwise match — v3's narrow Q-set + abelianization-based GQuotients
    handles them in minutes per H rather than v2legacy's hours.

    LEGACY RETIRED 2026-06-04: v3 is the production engine for ALL 2-factor jobs.
    The v3-only S2..S21 validation campaign confirmed v3 matches/supersedes legacy
    (the TG(8,9)/(8,11) crash + qfree3 rationale above is stale -- swap-iso rework
    fixed it).  predict_2factor_topt_v2legacy.py is KEPT (not on the production
    path) as an independent cross-check engine for completeness verification.
    Escape hatch: BUILD_SN_USE_V2LEGACY=1 restores the old heuristic routing (for
    A-B / cross-validation).  BUILD_SN_V3_ONLY=1 is now a no-op but still honoured.
    """
    if os.environ.get("BUILD_SN_USE_V2LEGACY") != "1":
        return False
    partition = j[3]
    if all(d <= 4 for d in partition) and len(left_combo) > 1:
        return False
    if len(left_combo) == 1:
        return True
    if any(d >= 9 for d in partition):
        return True
    if j[1] == "holt_split":
        return True
    return False


def build_dispatch_tasks(args, n, partitions, num_transitive, sn_out, n_dir,
                         pred_tmp, retry_round):
    """Build the list of (kind, key, cmd, timeout) tasks for one n at one
    retry round.  Returns (tasks, summary_counts, super_pack_idx_used).

    summary_counts is a dict suitable for the dispatch-log line:
      {batches, c2, c2_factor, burnside_m2, wreath_ra, wreath_via_2f,
       heavy_left}.

    super_pack_idx_used is the next free super-batch index, threaded through
    so the rebalance step doesn't collide.
    """
    # Importing here keeps the predict_2factor_topt entry-time cost out of
    # the runner package's import-time budget.
    from predict_2factor_topt import resolve_inputs as _resolve_inputs

    # ---- 1. classify all combos by route -------------------------------

    batch_groups = {}     # left_combo -> [(combo, mode, output_path, partition), ...]
    left_m_for_combo = {} # left_combo -> m_left
    burnside_combos = []  # [(combo, output_path, partition), ...]
    c2_combos = []
    c2_factor_combos = []
    bd8_combos = []        # pure (4,3)^k — run_b_d8_path.py
    elemab_combos = []     # pure (d,t)^k with (d,t) elementary abelian — run_b_elemab_path.py
    b_power_combos = []    # pure (d,t)^k with (d,t) in B_POWER_TG — run_b_power_path.py
    c2_glue_combos = []    # exactly one (2,1) block — run_c2_glue_path.py (no LEFT H-cache)
    c2_glue2_combos = []   # exactly two (2,1) blocks — run_c2_glue2_path.py (no LEFT H-cache)
    c3_glue_count = 0      # one degree-3 block, 3-coprime LEFT — rides the
                           # c2_glue chunks (same driver picks the RIGHT)
    identity_combos = []   # id_product/id_absorb/id_transfer —
                           # run_identity_path.py (pure Python, no GAP)
    wreath_combos = []
    wreath_via_2f_combos = []

    for partition in partitions:
        part_dir = n_dir / part_dirname(partition)
        for combo in combos_for_partition(partition, num_transitive):
            output_path = part_dir / f"{combo_filename(combo)}.g"
            rt = route(combo)
            if rt == "bootstrap":
                continue   # already done in main
            if output_path.exists():
                if is_complete_combo_file(output_path):
                    # During retry, only rerun missing/incomplete combos
                    # even if the original invocation used --force.
                    if retry_round > 0 or not args.force:
                        continue
                else:
                    output_path.unlink()   # truncated; will be recomputed
            if rt == "c2_fast":
                c2_combos.append((combo, output_path, partition))
                continue
            if rt == "c2_factor":
                c2_factor_combos.append((combo, output_path, partition))
                continue
            if rt == "b_power":
                b_power_combos.append((combo, output_path, partition))
                continue
            if rt == "bd8_fast":
                bd8_combos.append((combo, output_path, partition))
                continue
            if rt == "elemab_fast":
                elemab_combos.append((combo, output_path, partition))
                continue
            if rt in ("id_product", "id_absorb", "id_transfer"):
                identity_combos.append((combo, output_path, partition))
                continue
            if rt == "c2_glue":
                c2_glue_combos.append((combo, output_path, partition))
                continue
            if rt == "c3_glue":
                # Same driver, same batching; run_c2_glue_path.py's
                # choose_right picks the degree-3 block as RIGHT.
                c2_glue_combos.append((combo, output_path, partition))
                c3_glue_count += 1
                continue
            if rt == "c2_glue2":
                c2_glue2_combos.append((combo, output_path, partition))
                continue
            if rt == "wreath_ra":
                wreath_combos.append((combo, output_path, partition))
                continue
            if rt == "wreath_via_2factor":
                wreath_via_2f_combos.append((combo, output_path, partition))
                continue
            if rt == "burnside_m2":
                burnside_combos.append((combo, output_path, partition))
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

    # ---- 2. build 2-factor tasks (with super-batch packing) ------------

    tasks = []
    sb_jobs = args.super_batch_jobs
    sb_threshold = max(1, sb_jobs // 2)
    try:
        sb_max_groups = int(os.environ.get(
            "BUILD_SN_SUPER_MAX_GROUPS", str(max(2, args.workers))))
    except ValueError:
        sb_max_groups = max(2, args.workers)

    super_pack_groups = []
    super_pack_total_jobs = 0
    super_pack_idx = 0

    def flush_super_pack():
        nonlocal super_pack_groups, super_pack_total_jobs, super_pack_idx
        if not super_pack_groups:
            return
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
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * super_pack_total_jobs + 120
            outer_timeout = args.combo_timeout * super_pack_total_jobs + 240
        cmd = [sys.executable, "predict_2factor_topt.py",
               "--super-batch", str(sb_json), "--force",
               "--timeout", str(inner_timeout)]
        label = f"super_{super_pack_idx}({len(super_pack_groups)}grp,{super_pack_total_jobs}j)"
        tasks.append((TASK_KIND_SUPER_BATCH, label, cmd, outer_timeout))
        super_pack_idx += 1
        super_pack_groups = []
        super_pack_total_jobs = 0

    n_heavy_routed = 0

    # First: peel off v2legacy jobs into their own standalone batches per LEFT.
    new_batch_groups = {}
    for left_combo, group_jobs in batch_groups.items():
        v2_jobs = [j for j in group_jobs if _routes_to_v2(left_combo, j)]
        remaining = [j for j in group_jobs if not _routes_to_v2(left_combo, j)]
        if v2_jobs:
            batch_dir = pred_tmp / f"v2batch_n{n}_{combo_filename(left_combo)}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            jobs_json = batch_dir / "jobs.json"
            jobs_json.write_text(json.dumps([
                {"combo": list(combo), "mode": mode,
                 "output_path": str(out)}
                for combo, mode, out, _ in v2_jobs
            ]), encoding="utf-8")
            n_jobs_v2 = len(v2_jobs)
            if args.combo_timeout == 0:
                inner_timeout = 0
                outer_timeout = None
            else:
                inner_timeout = args.combo_timeout * n_jobs_v2
                outer_timeout = args.combo_timeout * n_jobs_v2 + 120
            cmd = [sys.executable, "predict_2factor_topt_v2legacy.py",
                   "--batch", str(jobs_json), "--force",
                   "--timeout", str(inner_timeout)]
            tasks.append((TASK_KIND_BATCH, f"v2_{combo_filename(left_combo)}",
                          cmd, outer_timeout))
        if remaining:
            new_batch_groups[left_combo] = remaining
    batch_groups = new_batch_groups

    for left_combo, group_jobs in batch_groups.items():
        n_jobs = len(group_jobs)
        m_left = left_m_for_combo.get(left_combo)
        lsize = left_class_count(left_combo, m_left, sn_out) if m_left else 0
        heavy = lsize > args.left_heavy_threshold
        if heavy:
            n_heavy_routed += 1
        if not heavy and sb_jobs > 1 and n_jobs <= sb_threshold:
            # Pack into super-batch.
            super_pack_groups.append((left_combo, group_jobs))
            super_pack_total_jobs += n_jobs
            if (super_pack_total_jobs >= sb_jobs
                    or (sb_max_groups > 0
                        and len(super_pack_groups) >= sb_max_groups)):
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
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * n_jobs
            outer_timeout = args.combo_timeout * n_jobs + 120
        cmd = [sys.executable, "predict_2factor_topt.py",
               "--batch", str(jobs_json), "--force",
               "--timeout", str(inner_timeout)]
        tasks.append((TASK_KIND_BATCH, combo_filename(left_combo), cmd, outer_timeout))
    flush_super_pack()

    # ---- 3. build single-task lists for c2 / c2_factor / burnside / wreath -

    if args.combo_timeout == 0:
        single_inner_timeout = 0
        single_outer_timeout = None
    else:
        single_inner_timeout = args.combo_timeout
        single_outer_timeout = args.combo_timeout + 60

    for combo, output_path, partition in c2_combos:
        cmd = [sys.executable, "run_c2_fast_path.py",
               "--combo", combo_filename(combo),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_C2, combo_filename(combo), cmd, single_outer_timeout))

    try:
        c2_factor_batch_jobs = int(os.environ.get(
            "BUILD_SN_C2_FACTOR_BATCH_JOBS",
            str(max(16, args.super_batch_jobs * 4))))
    except ValueError:
        c2_factor_batch_jobs = max(16, args.super_batch_jobs * 4)
    c2_factor_batch_jobs = max(1, c2_factor_batch_jobs)
    for batch_idx, start in enumerate(range(0, len(c2_factor_combos),
                                            c2_factor_batch_jobs)):
        chunk = c2_factor_combos[start:start + c2_factor_batch_jobs]
        c2f_dir = pred_tmp / f"c2_factor_n{n}_{batch_idx}"
        c2f_dir.mkdir(parents=True, exist_ok=True)
        jobs_json = c2f_dir / "jobs.json"
        jobs_json.write_text(json.dumps([
            {"combo": combo_filename(combo), "output_path": str(output_path)}
            for combo, output_path, _ in chunk
        ]), encoding="utf-8")
        if args.combo_timeout == 0:
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * len(chunk) + 120
            outer_timeout = inner_timeout + 120
        cmd = [sys.executable, "run_c2_factor_path.py",
               "--batch", str(jobs_json),
               "--timeout", str(inner_timeout)]
        tasks.append((TASK_KIND_C2_FACTOR_BATCH,
                      f"c2_factor_{batch_idx}({len(chunk)}j)",
                      cmd, outer_timeout))

    # Burnside m=2: v3 is the production engine (legacy retired 2026-06-04; v3
    # supports burnside_m2, verified on [8,9]_[8,9], [8,11]_[8,11]).  Escape hatch
    # BUILD_SN_USE_V2LEGACY=1 restores legacy routing.
    _burnside_script = ("predict_2factor_topt_v2legacy.py"
                        if os.environ.get("BUILD_SN_USE_V2LEGACY") == "1"
                        else "predict_2factor_topt.py")
    for combo, output_path, partition in burnside_combos:
        burn_dir = pred_tmp / f"burnside_n{n}_{combo_filename(combo)}"
        burn_dir.mkdir(parents=True, exist_ok=True)
        jobs_json = burn_dir / "jobs.json"
        jobs_json.write_text(json.dumps([{
            "combo": list(combo), "mode": "burnside_m2",
            "output_path": str(output_path)
        }]), encoding="utf-8")
        cmd = [sys.executable, _burnside_script,
               "--batch", str(jobs_json), "--force",
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_BATCH, combo_filename(combo), cmd, single_outer_timeout))

    # D_8 Frattini-factor fast path: one task per pure [4,3]^k combo.
    for combo, output_path, partition in bd8_combos:
        cmd = [sys.executable, "run_b_d8_path.py",
               "--combo", combo_filename(combo),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_BD8, combo_filename(combo), cmd, single_outer_timeout))

    # Elementary-abelian fast path: one task per pure [(d,t)]^k combo with
    # (d,t) in ELEM_AB_TG.  Uses GL_m(F_p) wr S_k orbit enumeration in
    # b_elemab_g.g via run_b_elemab_path.py.
    for combo, output_path, partition in elemab_combos:
        cmd = [sys.executable, "run_b_elemab_path.py",
               "--combo", combo_filename(combo),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_ELEMAB, combo_filename(combo), cmd, single_outer_timeout))

    # b_power pure-power engine: one task per pure (d,t)^k combo with (d,t)
    # in B_POWER_TG.  Handles C3/S3/C4/V4/D8 powers via b_power/power_dispatch.g
    # without going through the tower/fold pipeline.
    for combo, output_path, partition in b_power_combos:
        cmd = [sys.executable, "run_b_power_path.py",
               "--combo", combo_filename(combo),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_B_POWER, combo_filename(combo), cmd, single_outer_timeout))

    # C2-glue streaming path: combos with exactly one (2,1) block, batched
    # into shared GAP sessions (run_c2_glue_path.py --batch-json).  Per-job
    # cost scales with the n-2 source's class count (= lines streamed), so
    # jobs are weighed by it: sources above BUILD_SN_C2GLUE_HEAVY_SRC lines
    # get a standalone session (a monster like [2,1]_[4,3]^k must neither
    # wait behind nor stall small jobs) and are emitted first; the rest are
    # chunked to amortize GAP startup.
    try:
        c2_glue_batch_jobs = int(os.environ.get(
            "BUILD_SN_C2GLUE_BATCH_JOBS",
            str(max(16, args.super_batch_jobs * 4))))
    except ValueError:
        c2_glue_batch_jobs = max(16, args.super_batch_jobs * 4)
    c2_glue_batch_jobs = max(1, c2_glue_batch_jobs)
    try:
        c2_glue_heavy_src = int(os.environ.get(
            "BUILD_SN_C2GLUE_HEAVY_SRC", "2000"))
    except ValueError:
        c2_glue_heavy_src = 2000

    def _c2_glue_weight(combo):
        # Mirror run_c2_glue_path.py's choose_right preference so the weight
        # is measured on the source the engine will actually stream:
        # (2,1) -> n-2 source, else the degree-3 block -> n-3 source.
        x = list(combo)
        for right in ((2, 1), (3, 2), (3, 1)):
            if x.count(right) == 1:
                x.remove(right)
                break
        else:
            return 0
        return left_class_count(tuple(x), sum(d for d, _ in x), sn_out)

    # TRUE monsters (above BUILD_SN_C2GLUE_SHARD_SRC source lines) fan out
    # over source line ranges via the engine's --shards (exact merge: the
    # per-line Goursat work is entry-local).  (3,1) RIGHTs are excluded:
    # their class_sum is computed in closed form from the WHOLE source's
    # header (per-shard closed forms would overcount), and their textual
    # stream is I/O-bound anyway (n=23 [3,1]_[4,3]^5 = 1.6M lines in ~34s).
    try:
        c2_glue_shard_src = int(os.environ.get(
            "BUILD_SN_C2GLUE_SHARD_SRC", "100000"))
    except ValueError:
        c2_glue_shard_src = 100000
    try:
        c2_glue_shards = int(os.environ.get("BUILD_SN_C2GLUE_SHARDS", "6"))
    except ValueError:
        c2_glue_shards = 6

    def _c2_glue_right(combo):
        # run_c2_glue_path.py's choose_right preference order.
        for right in ((2, 1), (3, 2), (3, 1)):
            if combo.count(right) == 1:
                return right
        return None

    c2_glue_chunks = []
    c2_glue_light = []
    for combo, output_path, partition in sorted(
            c2_glue_combos, key=lambda t: -_c2_glue_weight(t[0])):
        w = _c2_glue_weight(combo)
        if (w > c2_glue_shard_src and c2_glue_shards > 1
                and _c2_glue_right(combo) != (3, 1)):
            if args.combo_timeout == 0:
                inner_timeout = 0
                outer_timeout = None
            else:
                inner_timeout = args.combo_timeout + 120
                outer_timeout = inner_timeout + 120
            cmd = [sys.executable, "run_c2_glue_path.py",
                   "--combo", combo_filename(combo),
                   "--output-path", str(output_path),
                   "--shards", str(max(1, c2_glue_shards)),
                   "--timeout", str(inner_timeout)]
            tasks.append((TASK_KIND_C2_GLUE2_SHARDED,
                          f"c2_glue_shard_{combo_filename(combo)}",
                          cmd, outer_timeout))
        elif w > c2_glue_heavy_src:
            c2_glue_chunks.append([(combo, output_path, partition)])
        else:
            c2_glue_light.append((combo, output_path, partition))
    for start in range(0, len(c2_glue_light), c2_glue_batch_jobs):
        c2_glue_chunks.append(c2_glue_light[start:start + c2_glue_batch_jobs])
    for batch_idx, chunk in enumerate(c2_glue_chunks):
        cg_dir = pred_tmp / f"c2_glue_n{n}_{batch_idx}"
        cg_dir.mkdir(parents=True, exist_ok=True)
        jobs_json = cg_dir / "jobs.json"
        jobs_json.write_text(json.dumps([
            {"combo": combo_filename(combo), "output_path": str(output_path)}
            for combo, output_path, _ in chunk
        ]), encoding="utf-8")
        if args.combo_timeout == 0:
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * len(chunk) + 120
            outer_timeout = inner_timeout + 120
        cmd = [sys.executable, "run_c2_glue_path.py",
               "--batch-json", str(jobs_json),
               "--timeout", str(inner_timeout)]
        tasks.append((TASK_KIND_C2_GLUE_BATCH,
                      f"c2_glue_{batch_idx}({len(chunk)}j)",
                      cmd, outer_timeout))

    # C2^2-glue streaming path: combos with exactly two (2,1) blocks (the
    # peel_c2_pair family), batched like c2_glue.  Weight = the n-4 source's
    # class count; heavy sources get a standalone session, and TRUE monsters
    # (above BUILD_SN_C2GLUE2_SHARD_SRC lines) use the engine's --shards
    # line-range fan-out so a 3.88M-class job doesn't ride one core.
    def _c2_glue2_weight(combo):
        x = list(combo)
        x.remove((2, 1))
        x.remove((2, 1))
        return left_class_count(tuple(x), sum(d for d, _ in x), sn_out)

    try:
        c2_glue2_shard_src = int(os.environ.get(
            "BUILD_SN_C2GLUE2_SHARD_SRC", "20000"))
    except ValueError:
        c2_glue2_shard_src = 20000
    try:
        c2_glue2_shards = int(os.environ.get(
            "BUILD_SN_C2GLUE2_SHARDS", "4"))
    except ValueError:
        c2_glue2_shards = 4

    c2_glue2_chunks = []
    c2_glue2_light = []
    for combo, output_path, partition in sorted(
            c2_glue2_combos, key=lambda t: -_c2_glue2_weight(t[0])):
        w = _c2_glue2_weight(combo)
        if w > c2_glue2_shard_src:
            # standalone sharded session
            if args.combo_timeout == 0:
                inner_timeout, outer_timeout = 0, None
            else:
                inner_timeout = args.combo_timeout + 120
                outer_timeout = inner_timeout + 120
            cmd = [sys.executable, "run_c2_glue2_path.py",
                   "--combo", combo_filename(combo),
                   "--output-path", str(output_path),
                   "--shards", str(max(1, c2_glue2_shards)),
                   "--timeout", str(inner_timeout)]
            tasks.append((TASK_KIND_C2_GLUE2_SHARDED,
                          f"c2_glue2_shard_{combo_filename(combo)}",
                          cmd, outer_timeout))
        elif w > c2_glue_heavy_src:
            c2_glue2_chunks.append([(combo, output_path, partition)])
        else:
            c2_glue2_light.append((combo, output_path, partition))
    for start in range(0, len(c2_glue2_light), c2_glue_batch_jobs):
        c2_glue2_chunks.append(c2_glue2_light[start:start + c2_glue_batch_jobs])
    for batch_idx, chunk in enumerate(c2_glue2_chunks):
        cg_dir = pred_tmp / f"c2_glue2_n{n}_{batch_idx}"
        cg_dir.mkdir(parents=True, exist_ok=True)
        jobs_json = cg_dir / "jobs.json"
        jobs_json.write_text(json.dumps([
            {"combo": combo_filename(combo), "output_path": str(output_path)}
            for combo, output_path, _ in chunk
        ]), encoding="utf-8")
        if args.combo_timeout == 0:
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * len(chunk) + 120
            outer_timeout = inner_timeout + 120
        cmd = [sys.executable, "run_c2_glue2_path.py",
               "--batch-json", str(jobs_json),
               "--timeout", str(inner_timeout)]
        tasks.append((TASK_KIND_C2_GLUE2_BATCH,
                      f"c2_glue2_{batch_idx}({len(chunk)}j)",
                      cmd, outer_timeout))

    # Identity routes: pure-Python textual materialization from lower-n
    # files (run_identity_path.py, no GAP).  Cost is dominated by the bytes
    # written, so jobs are weighed by projected output lines (product of the
    # factor counts / the transfer target's count); TRUE monsters (a
    # multi-M-line product is a ~1 GB write) get a standalone task so they
    # don't stall a chunk of thousands of instant jobs.
    try:
        identity_batch_jobs = int(os.environ.get(
            "BUILD_SN_IDENTITY_BATCH_JOBS", "200"))
    except ValueError:
        identity_batch_jobs = 200
    identity_batch_jobs = max(1, identity_batch_jobs)
    try:
        identity_heavy_out = int(os.environ.get(
            "BUILD_SN_IDENTITY_HEAVY_OUT", "500000"))
    except ValueError:
        identity_heavy_out = 500000

    _identity_weights = {}
    _identity_src_counts = {}   # factor/target combo -> # deduped (factors
                                # like [3,1] recur across thousands of combos)

    def _identity_src_count(c):
        if c not in _identity_src_counts:
            _identity_src_counts[c] = left_class_count(
                c, sum(d for d, _ in c), sn_out)
        return _identity_src_counts[c]

    def _identity_weight(combo):
        if combo in _identity_weights:
            return _identity_weights[combo]
        from run_identity_path import classify_identity
        ident = classify_identity(combo)
        w = 0
        if ident is not None:
            if ident["kind"] == "id_transfer":
                w = _identity_src_count(ident["target"])
            else:
                w = 1
                for f in ident["factors"]:
                    c = _identity_src_count(f)
                    if c == 0:
                        w = 0
                        break
                    w *= c
        _identity_weights[combo] = w
        return w

    identity_chunks = []
    identity_light = []
    for item in sorted(identity_combos,
                       key=lambda t: -_identity_weight(t[0])):
        if _identity_weight(item[0]) > identity_heavy_out:
            identity_chunks.append([item])
        else:
            identity_light.append(item)
    for start in range(0, len(identity_light), identity_batch_jobs):
        identity_chunks.append(identity_light[start:start + identity_batch_jobs])
    for batch_idx, chunk in enumerate(identity_chunks):
        id_dir = pred_tmp / f"identity_n{n}_{batch_idx}"
        id_dir.mkdir(parents=True, exist_ok=True)
        jobs_json = id_dir / "jobs.json"
        jobs_json.write_text(json.dumps([
            {"combo": combo_filename(combo), "output_path": str(output_path)}
            for combo, output_path, _ in chunk
        ]), encoding="utf-8")
        if args.combo_timeout == 0:
            inner_timeout = 0
            outer_timeout = None
        else:
            inner_timeout = args.combo_timeout * len(chunk) + 120
            outer_timeout = inner_timeout + 120
        cmd = [sys.executable, "run_identity_path.py",
               "--batch-json", str(jobs_json),
               "--timeout", str(inner_timeout)]
        tasks.append((TASK_KIND_IDENTITY_BATCH,
                      f"identity_{batch_idx}({len(chunk)}j)",
                      cmd, outer_timeout))

    for combo, output_path, partition in wreath_combos:
        cmd = [sys.executable, "predict_full_general_wreath.py",
               "--combo", combo_filename(combo),
               "--target-n", str(n),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_WREATH, combo_filename(combo), cmd, single_outer_timeout))

    for combo, output_path, partition in wreath_via_2f_combos:
        cmd = [sys.executable, "run_wreath_via_2factor.py",
               "--combo", combo_filename(combo),
               "--target-n", str(n),
               "--output-path", str(output_path),
               "--timeout", str(single_inner_timeout)]
        tasks.append((TASK_KIND_WREATH_VIA_2F, combo_filename(combo),
                      cmd, single_outer_timeout))

    # ---- 4. sort by priority: wreath first (long tail), then c2, then batches.
    # Stable sort preserves intra-kind order so deterministic.
    _priority = {
        TASK_KIND_IDENTITY_BATCH: 0,
        TASK_KIND_WREATH: 0, TASK_KIND_WREATH_VIA_2F: 0,
        TASK_KIND_BD8: 0, TASK_KIND_ELEMAB: 0, TASK_KIND_B_POWER: 0,
        TASK_KIND_C2_GLUE_BATCH: 0,
        TASK_KIND_C2_GLUE2_SHARDED: 0, TASK_KIND_C2_GLUE2_BATCH: 0,
        TASK_KIND_C2: 1, "c2_factor": 1, TASK_KIND_C2_FACTOR_BATCH: 1,
        TASK_KIND_SUPER_BATCH: 2, TASK_KIND_BATCH: 2,
    }
    tasks.sort(key=lambda t: _priority.get(t[0], 3))

    summary_counts = {
        "batches": len(batch_groups),
        "c2": len(c2_combos),
        "c2_factor": len(c2_factor_combos),
        "bd8": len(bd8_combos),
        "elemab": len(elemab_combos),
        "b_power": len(b_power_combos),
        "c2_glue": len(c2_glue_combos) - c3_glue_count,
        "c2_glue2": len(c2_glue2_combos),
        "c3_glue": c3_glue_count,
        "identity": len(identity_combos),
        "burnside_m2": len(burnside_combos),
        "wreath_ra": len(wreath_combos),
        "wreath_via_2f": len(wreath_via_2f_combos),
        "heavy_left": n_heavy_routed,
    }
    return tasks, summary_counts, super_pack_idx


def rebalance_super_batches(tasks, args, pred_tmp, n, super_pack_idx):
    """If the task count is below worker count, split the largest multi-group
    super-batches in half until either tasks >= workers or no super-batch has
    more than one group.  Mutates `tasks` in place; returns the new
    `super_pack_idx` plus the number of splits performed.
    """
    def _split_largest():
        nonlocal super_pack_idx
        sb_indices = [i for i, t in enumerate(tasks) if t[0] == TASK_KIND_SUPER_BATCH]
        if not sb_indices:
            return False

        def n_groups(i):
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
        new_a = (TASK_KIND_SUPER_BATCH,
                 f"super_{super_pack_idx}({len(left_groups)}grp,{n_jobs_a}j,split)",
                 [sys.executable, "predict_2factor_topt.py",
                  "--super-batch", str(sb_json_a), "--force",
                  "--timeout", str(inner_to)],
                 outer_to)
        new_b = (TASK_KIND_SUPER_BATCH,
                 f"super_{super_pack_idx + 1}({len(right_groups)}grp,{n_jobs_b}j,split)",
                 [sys.executable, "predict_2factor_topt.py",
                  "--super-batch", str(sb_json_b), "--force",
                  "--timeout", str(inner_to)],
                 outer_to)
        tasks.pop(target)
        tasks.append(new_a)
        tasks.append(new_b)
        super_pack_idx += 2
        return True

    rebalance_iters = 0
    while len(tasks) < args.workers and rebalance_iters < args.workers * 4:
        if not _split_largest():
            break
        rebalance_iters += 1
    return super_pack_idx, rebalance_iters
