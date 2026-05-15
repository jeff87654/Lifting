"""Route selection and per-combo dispatch.

`route(combo)` picks the cheapest path that applies to a combo: one of
`bootstrap`, `c2_fast`, `bd8_fast`, `elemab_fast`, `distinguished`,
`holt_split`, `burnside_m2`, `wreath_ra`, `wreath_via_2factor`.

`run_combo(...)` actually executes the picked route — invokes the relevant
predictor, handles fall-through from the fast paths to the generic routes
(c2_fast/bd8_fast/elemab_fast all fall through to a regular route on
predictor failure), and dispatches the two-step `wreath_via_2factor`
pipeline through `_run_wreath_via_2factor`.

The 2026-05-11 c2_factor route is gone — both `route()` and `run_combo()`
no longer mention it.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from runner.combos import combo_filename
from runner.constants import (
    ELEM_AB_TG,
    FORCE_WREATH_2F,
    FORCE_WREATH_RA,
    ROOT,
    WREATH_2F_MIN_N,
)
from runner.predictors import run_predictor


def route(combo):
    """Return route name string."""
    if len(combo) == 1:
        return "bootstrap"
    partition = sorted([d for d, _ in combo], reverse=True)
    # C_2 fast path is intended for pure C_2^n only (= partition is all 2's).
    # Mixed combos with non-2 prefix go through the regular routes.
    if len(partition) >= 2 and all(d == 2 for d in partition):
        return "c2_fast"
    # D_8 Frattini-factor fast path: pure [4,3]^k (T(4,3) = D_8).
    if all(pair == (4, 3) for pair in combo):
        return "bd8_fast"
    # Elementary abelian fast path: pure [(d,t)]^k with (d,t) in ELEM_AB_TG.
    # Generalizes b21 ([2,1]^k) to other elem-ab factors via GL_m(F_p) wr S_k
    # orbit enumeration in b_elemab.g.
    if all(pair == combo[0] for pair in combo) and combo[0] in ELEM_AB_TG:
        return "elemab_fast"
    # NOTE: c2_factor route removed 2026-05-11.  It used naive
    # RepresentativeAction-in-S_n dedup that ran for hours per combo on
    # [2,1]_[18,*] etc.  `[2,1]_[Q,*]` now falls through to "distinguished"
    # which uses proper Goursat dedup via the 2-factor predictor.
    clusters = Counter(combo)
    if any(mult == 1 for mult in clusters.values()):
        return "distinguished"
    if len(clusters) >= 2:
        return "holt_split"
    sp, mult = next(iter(clusters.items()))
    if mult == 2:
        return "burnside_m2"
    # Single-cluster m>=3.  The 2-step pipeline:
    #   (1) predict_2factor_topt --mode holt_split  -> emits W_LR-deduped
    #       candidates as fps.g (uses qfree3/H_CACHE optimizations).
    #   (2) predict_full_general_wreath --candidates-from fps.g  -> applies
    #       the bucketize + RA-in-W dedup so the final count is correctly
    #       deduped under the full block-wreath ambient W = N_T wr S_m.
    #
    # That pipeline pays two full GAP startups and two materialization passes.
    # It wins on the large repeated-cluster cases it was built for, but it is
    # much slower than the direct wreath route for small n where the final
    # candidate list has only tens or hundreds of groups.
    if FORCE_WREATH_RA:
        return "wreath_ra"
    if FORCE_WREATH_2F:
        return "wreath_via_2factor"
    total_n = sum(d for d, _ in combo)
    if total_n < WREATH_2F_MIN_N:
        return "wreath_ra"
    return "wreath_via_2factor"


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

    # D_8 Frattini-factor fast path (pure [4,3]^k).
    if route_name == "bd8_fast":
        result = run_predictor("run_b_d8_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": "bd8_fast", "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Fall through to wreath path on failure.
        route_name = "wreath_ra"

    # Elementary abelian fast path (pure [(d,t)]^k for non-C_2 elem-ab).
    if route_name == "elemab_fast":
        result = run_predictor("run_b_elemab_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": "elemab_fast", "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Fall through to wreath path on failure.
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

    if route_name == "wreath_via_2factor":
        return _run_wreath_via_2factor(combo_str, output_path, n, timeout)

    return {"route": route_name, "error": "unhandled route", "count": 0,
            "elapsed_s": 0}


def _run_wreath_via_2factor(combo_str, output_path, n, timeout):
    """Two-step pipeline for single-cluster m>=3:
        Step 1: predict_2factor_topt --mode holt_split --emit-generators
                produces fps.g of W_LR-deduped candidates (uses qfree3 cache
                wins).
        Step 2: predict_full_general_wreath --candidates-from fps.g
                buckets + RA-deduplicates under W = N_T wr S_m, writes the
                final legacy-format file at output_path.
    The total elapsed time is the sum; the count returned is from step 2."""
    route_name = "wreath_via_2factor"
    t0 = time.time()

    # Step 1: 2-factor candidate generation.  Don't pass --output-path so
    # predict_2factor doesn't compose a (W_LR-deduped, over-counted) legacy
    # file; we only want fps.g to feed into step 2.
    step1_args = [sys.executable, str(ROOT / "predict_2factor_topt.py"),
                  "--combo", combo_str,
                  "--mode", "holt_split",
                  "--emit-generators",
                  "--force",
                  "--timeout", str(timeout)]
    try:
        proc1 = subprocess.run(step1_args, capture_output=True, text=True,
                                timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"route": route_name, "error": "step1 timeout", "count": 0,
                "elapsed_s": time.time() - t0}
    if proc1.returncode != 0:
        return {"route": route_name,
                "error": {"step": 1, "rc": proc1.returncode,
                          "stderr": proc1.stderr[-500:],
                          "stdout": proc1.stdout[-500:]},
                "count": 0, "elapsed_s": time.time() - t0}
    try:
        result1 = json.loads(proc1.stdout)
    except json.JSONDecodeError:
        return {"route": route_name,
                "error": {"step": 1, "msg": "json parse",
                          "stdout": proc1.stdout[-500:]},
                "count": 0, "elapsed_s": time.time() - t0}
    fps_g = result1.get("generators_file")
    if not fps_g or not Path(fps_g).exists():
        return {"route": route_name,
                "error": {"step": 1, "msg": "no generators_file",
                          "result": result1},
                "count": 0, "elapsed_s": time.time() - t0}

    # Step 2: bucketize + RA-in-W dedup.
    step2_args = [sys.executable, str(ROOT / "predict_full_general_wreath.py"),
                  "--combo", combo_str,
                  "--target-n", str(n),
                  "--candidates-from", fps_g,
                  "--output-path", str(output_path),
                  "--timeout", str(timeout)]
    try:
        proc2 = subprocess.run(step2_args, capture_output=True, text=True,
                                timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"route": route_name, "error": "step2 timeout", "count": 0,
                "elapsed_s": time.time() - t0}
    if proc2.returncode != 0:
        return {"route": route_name,
                "error": {"step": 2, "rc": proc2.returncode,
                          "stderr": proc2.stderr[-500:],
                          "stdout": proc2.stdout[-500:]},
                "count": 0, "elapsed_s": time.time() - t0}
    try:
        result2 = json.loads(proc2.stdout)
    except json.JSONDecodeError:
        return {"route": route_name,
                "error": {"step": 2, "msg": "json parse",
                          "stdout": proc2.stdout[-500:]},
                "count": 0, "elapsed_s": time.time() - t0}
    if "error" in result2:
        return {"route": route_name,
                "error": {"step": 2, "result": result2},
                "count": 0, "elapsed_s": time.time() - t0}
    return {"route": route_name,
            "count": result2["predicted"],
            "elapsed_s": time.time() - t0,
            "n_materialized_2factor": result1.get("orbits"),
            "n_distinct_after_RA": result2.get("n_distinct")}
