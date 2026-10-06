"""Route selection and per-combo dispatch.

`route(combo)` picks the cheapest path that applies to a combo: one of
`bootstrap`, `c2_fast`, `b_power`, `bd8_fast`, `elemab_fast`, `c2_glue`,
`c2_glue2`, `c3_glue`, `distinguished`, `peel_c2_pair`, `holt_split`,
`burnside_m2`, `wreath_ra`, `wreath_via_2factor`.

`peel_c2_pair` added 2026-05-23 for combos with `(2,1)^2 + heavy^k` and no
mult-1 species (where `distinguished` doesn't apply).  Peels both (2,1)s
to RIGHT as a subgroup-list (RIGHT_combo=[2,1]_[2,1], 2 entries) so the
heavy cluster becomes LEFT and benefits from cheaper LEFT-side H_CACHE
per-entry cost.  Confirmed 6.6x speedup on [2,1]_[2,1]_[8,22]_[8,22]
(4.7h holt_split -> 42min peel_c2_pair).

The 2026-05-15 `b2g3_v3` route was removed 2026-05-21: it produced source
files in a format `predict_2factor_topt.py:resolve_inputs` didn't accept,
which cascaded into "resolve_inputs failed: unknown mode: b2g3_v3" errors
at higher n.  The mixed Frattini / D_8+S_4 / pure-S_4 combos it claimed
now fall through to the regular `distinguished`/`holt_split` routes.

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
    B_POWER_TG,
    DISABLE_B_POWER,
    DISABLE_C2_GLUE,
    DISABLE_C2_GLUE2,
    DISABLE_C3_GLUE,
    DISABLE_IDENTITY,
    ELEM_AB_TG,
    FORCE_WREATH_2F,
    FORCE_WREATH_RA,
    ROOT,
    TG_ORDERS_PATH,
    WREATH_2F_MIN_N,
)
from runner.predictors import run_predictor


_TG_ORDERS = None


def _tg_order(d, t):
    """Size(TransitiveGroup(d,t)) from database/tg_orders.json, or None when
    the table is missing / doesn't cover (d,t) (callers must treat None as
    'not eligible' so a stale table degrades to the general routes)."""
    global _TG_ORDERS
    if _TG_ORDERS is None:
        try:
            _TG_ORDERS = json.loads(TG_ORDERS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _TG_ORDERS = {}
    lst = _TG_ORDERS.get(str(d))
    if lst is None or not (1 <= t <= len(lst)):
        return None
    return lst[t - 1]


def c3_glue_capable(combo):
    """True iff the c3_glue streaming route owns this combo: exactly one
    degree-3 block against a LEFT with every species order coprime to 3.
    The coprimality test is EXACT (not just sufficient): every FPF class
    surjects onto each block constituent, so 3 | |H_L| iff some LEFT species
    order is divisible by 3.  The (2,1)-count gate lives in route() — counts
    1/2 belong to c2_glue/c2_glue2, which stream the cheaper n-2/n-4
    sources."""
    if len(combo) < 2:
        return False
    if sum(1 for d, _ in combo if d == 3) != 1:
        return False
    for d, t in combo:
        if d == 3:
            continue
        order = _tg_order(d, t)
        if order is None or order % 3 == 0:
            return False
    return True


def b_power_capable(combo):
    """True iff the b_power pure-power engine should own this combo.
    Pure power TG(d,t)^k with k >= 2 and (d,t) in B_POWER_TG."""
    if DISABLE_B_POWER:
        return False
    if len(combo) < 2:
        return False
    if not all(pair == combo[0] for pair in combo):
        return False
    return combo[0] in B_POWER_TG


def _classify_split(combo):
    """Split-geometry class, shared by route() and the run_combo() fast-path
    fall-throughs.  Returns one of: distinguished, peel_c2_pair, holt_split,
    burnside_m2, wreath.  "wreath" (single species, mult >= 3) defers the
    wreath_ra vs wreath_via_2factor choice to the caller (see _resolve_wreath).

    NOTE: c2_factor route removed 2026-05-11 (naive RepresentativeAction-in-S_n
    dedup ran for hours); `[2,1]_[Q,*]` now falls through to "distinguished".
    """
    clusters = Counter(combo)
    if any(mult == 1 for mult in clusters.values()):
        return "distinguished"
    # (2,1)^2 + heavy^k: peel both (2,1)s to RIGHT so the heavy cluster becomes
    # LEFT (cheaper H_CACHE/entry).  Confirmed 6.6x on [2,1]_[2,1]_[8,22]_[8,22]
    # (4.7h holt_split -> 42min peel_c2_pair).  GATE FIXED 2026-05-23: was `>= 2`,
    # which over-counted mult=3 cases like [2,1]^3 [3,1]^2 (+2) / [2,1]^3 [3,2]^2
    # (+38) — peeling 2 of 3 strands a [2,1] on LEFT.  Restricted to mult EXACTLY 2.
    if clusters.get((2, 1), 0) == 2 and len(clusters) >= 2:
        return "peel_c2_pair"
    if len(clusters) >= 2:
        return "holt_split"
    sp, mult = next(iter(clusters.items()))
    if mult == 2:
        return "burnside_m2"
    return "wreath"


def _resolve_wreath(combo, honor_force=True):
    """Resolve a single-species wreath combo to wreath_ra or wreath_via_2factor.

    The 2-step wreath_via_2factor pipeline:
      (1) predict_2factor_topt --mode holt_split -> emits W_LR-deduped candidates
          as fps.g (qfree3/H_CACHE optimizations);
      (2) predict_full_general_wreath --candidates-from fps.g -> bucketize +
          RA-in-W dedup, correctly deduped under the block-wreath W = N_T wr S_m.
    It pays two GAP startups + two materialization passes; it wins on large
    repeated-cluster cases but loses to the direct wreath route for small n.

    `honor_force=False` reproduces the b_power fall-through, which historically
    ignores the FORCE_WREATH_* overrides and decides purely on size.
    """
    if honor_force and FORCE_WREATH_RA:
        return "wreath_ra"
    if honor_force and FORCE_WREATH_2F:
        return "wreath_via_2factor"
    total_n = sum(d for d, _ in combo)
    return "wreath_ra" if total_n < WREATH_2F_MIN_N else "wreath_via_2factor"


_classify_identity = None


def identity_kind(combo):
    """The identity route owning this combo ("id_product" / "id_absorb" /
    "id_transfer"), or None.  Classification lives in run_identity_path.py
    (lazy import) so the router and the emitter can never skew."""
    global _classify_identity
    if _classify_identity is None:
        from run_identity_path import classify_identity
        _classify_identity = classify_identity
    ident = _classify_identity(combo)
    return ident["kind"] if ident else None


def route(combo):
    """Return route name string.  Four transparent tiers: (1) fast paths,
    (1b) verified counting identities, (2) split geometry (_classify_split),
    (3) wreath resolution."""
    # ---- Tier 1: fast paths ----
    if len(combo) == 1:
        return "bootstrap"
    partition = sorted([d for d, _ in combo], reverse=True)
    # C_2 fast path is intended for pure C_2^n only (= partition is all 2's).
    # Mixed combos with non-2 prefix go through the regular routes.
    if len(partition) >= 2 and all(d == 2 for d in partition):
        return "c2_fast"
    # b_power pure-power engine: pure TG(d,t)^k for k >= 2 and (d,t) in
    # B_POWER_TG = {(3,1) C3, (3,2) S3, (4,1) C4, (4,2) V4, (4,3) D8}.
    # Sits before bd8_fast / elemab_fast so it preempts them for these cases.
    if b_power_capable(combo):
        return "b_power"
    # D_8 Frattini-factor fast path: pure [4,3]^k (T(4,3) = D_8).
    if all(pair == (4, 3) for pair in combo):
        return "bd8_fast"
    # Elementary abelian fast path: pure [(d,t)]^k with (d,t) in ELEM_AB_TG.
    # Generalizes b21 ([2,1]^k) to other elem-ab factors via GL_m(F_p) wr S_k.
    if all(pair == combo[0] for pair in combo) and combo[0] in ELEM_AB_TG:
        return "elemab_fast"
    # ---- Tier 1b: verified counting identities (2026-07-02) ----
    # id_product (coprime-cluster product), id_absorb (A_d/simple block
    # absorption), id_transfer (D_2d/S_d block <-> (2,1) block) — pure-Python
    # textual materialization from already-built lower-n files, no GAP.  All
    # three verified exact (deduped + labelled) against every applicable
    # s2..s22 combo; see run_identity_path.py.  Placed before the glue
    # streams so e.g. [2,1]_[4,3]^4_[5,1] becomes a free product instead of
    # a c2_glue GAP stream.  Opt-out: BUILD_SN_IDENTITY=0.
    if not DISABLE_IDENTITY:
        kind = identity_kind(combo)
        if kind:
            return kind
    return _route_glue_or_split(combo)


def _route_glue_or_split(combo):
    """Tiers 2-3 plus the glue streams: the route a combo takes when no fast
    path / identity claims it (also the fall-back when the identity emitter
    reports an error, e.g. a missing source file)."""
    # C2-glue streaming path (2026-06-09): exactly one (2,1) block forces the
    # Goursat glue quotient set to {1, C2} against ANY other content, so every
    # pairing is entry-local (Aut(C2)=1) and the LEFT H-cache is skipped
    # entirely — run_c2_glue_path.py streams the n-2 source file.  These
    # combos previously routed to `distinguished` (species mult 1).
    # Opt-out: BUILD_SN_C2GLUE=0.
    if not DISABLE_C2_GLUE and combo.count((2, 1)) == 1:
        return "c2_glue"
    # C2^2-glue streaming path (2026-06-11): exactly two (2,1) blocks + a
    # non-degree-2 cluster (previously peel_c2_pair).  RIGHT structure is
    # fixed (two FPF classes: C2^2 and the diagonal C2; glue {1, C2, V4};
    # block-swap Aut collapse hand-derived), so every class is entry-local
    # per LEFT line — run_c2_glue2_path.py streams the n-4 source, NO LEFT
    # H-cache.  Validated 2518/2518 exact (deduped + class_sum) vs
    # fresh_0604 n=8..17.  Opt-out: BUILD_SN_C2GLUE2=0.
    if (not DISABLE_C2_GLUE2 and combo.count((2, 1)) == 2
            and len(combo) > 2):
        return "c2_glue2"
    # C3/S3-glue streaming path (2026-07-02): exactly one degree-3 block
    # against a 3-coprime LEFT forces the glue set to {1} (C3 RIGHT) or
    # {1, C2} (S3 RIGHT, kernel A3 characteristic), so the same entry-local
    # streaming engine applies — run_c2_glue_path.py picks the 3-block as
    # RIGHT and streams the n-3 source.  Kills the D8^k LEFT H-caches on
    # odd-n monsters like [3,t]_[4,3]^5.  The (2,1)-count guard keeps this
    # clause from re-enabling a stream the user opted out of above (the
    # engine's RIGHT preference is (2,1) > (3,2) > (3,1)).
    # Opt-out: BUILD_SN_C3GLUE=0.
    if (not DISABLE_C3_GLUE and combo.count((2, 1)) not in (1, 2)
            and c3_glue_capable(combo)):
        return "c3_glue"

    # ---- Tier 2: split geometry ----
    cls = _classify_split(combo)
    if cls != "wreath":
        return cls

    # ---- Tier 3: wreath resolution (single species, mult >= 3) ----
    return _resolve_wreath(combo)


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
        # Fall through to other routes if C_2 path rejected.  This path keeps
        # its historical wreath mapping: a wreath combo falls to wreath_ra
        # (the direct route), not the 2-step pipeline.
        cls = _classify_split(combo)
        route_name = "wreath_ra" if cls == "wreath" else cls

    # b_power pure-power engine (pure TG(d,t)^k for k >= 2, (d,t) in B_POWER_TG).
    if route_name == "b_power":
        result = run_predictor("run_b_power_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": "b_power", "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Fall through: pick the legacy route this combo would otherwise take.
        # Historically this path decides wreath purely on size (it does NOT
        # honor the FORCE_WREATH_* overrides) -> honor_force=False.
        cls = _classify_split(combo)
        route_name = _resolve_wreath(combo, honor_force=False) \
            if cls == "wreath" else cls

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

    # Identity emitters (pure-Python textual materialization, no GAP).
    if route_name in ("id_product", "id_absorb", "id_transfer"):
        result = run_predictor("run_identity_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": route_name, "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Missing/corrupt source files etc.: fall back to the route the
        # combo would take without the identity tier.
        route_name = _route_glue_or_split(combo)

    # C2-glue streaming path (exactly one (2,1) block).
    if route_name == "c2_glue2":
        result = run_predictor("run_c2_glue2_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": "c2_glue2", "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Engine-side NA falls back to the general split route.
        route_name = _classify_split(combo)

    if route_name in ("c2_glue", "c3_glue"):
        glue_route = route_name
        result = run_predictor("run_c2_glue_path.py", combo_str,
                                output_path, timeout=timeout)
        if "error" not in result:
            return {"route": glue_route, "count": result["predicted"],
                    "elapsed_s": result["elapsed_s"]}
        # Fall through to the split-geometry route on failure (these combos
        # are all species-mult-1 -> distinguished).
        route_name = _classify_split(combo)

    if route_name in ("distinguished", "holt_split", "burnside_m2", "peel_c2_pair"):
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
