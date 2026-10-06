"""Module-level constants for the build runner.

This module exists so paths, the OEIS reference table, the elementary-abelian
transitive-group whitelist, and the static environment-variable tunables all
live in one place.  Two things deliberately do NOT live here:

  - argparse defaults — they're CLI knobs, not constants
  - env-vars whose default depends on parsed args (BUILD_SN_SUPER_MAX_GROUPS
    uses args.workers; BUILD_SN_C2_FACTOR_BATCH_JOBS uses args.super_batch_jobs).
    Those are resolved in `runner.scheduler` once args are available.
"""
from __future__ import annotations
import os
from pathlib import Path


# --- Paths ----------------------------------------------------------------

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    """Windows path -> Cygwin path.  Used everywhere we hand a path to bash."""
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


# --- OEIS A000638 ---------------------------------------------------------

# Number of subgroups of S_n up to conjugacy.  Used to validate the per-n
# total via FPF(n) = A000638(n) - A000638(n-1).
A000638 = {
    0: 1, 1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96,
    8: 296, 9: 554, 10: 1593, 11: 3094, 12: 10723, 13: 20832,
    14: 75154, 15: 159129, 16: 686165, 17: 1466358, 18: 7274651,
    # n=19,20,21: first independent computations (this project), not yet in OEIS.
    # 19 confirmed 2026-05-19/20; 20 confirmed 2026-05-20 (V_4 fast-path rerun).
    # 21: CORRECTED 2026-06-04 to FPF(21)=140,399,143 => A000638(21)=245393739.
    #     (2026-06-09: the value first recorded here, 245393959, was an ARITHMETIC
    #     SLIP — 140,399,143 + 104,994,596 mis-added; it made the completed
    #     2026-06-08 fresh_0604 S21 run print a spurious MISMATCH even though it
    #     reproduced v3only exactly on all 170,119 combos.)  The prior
    #     235181063 (FPF=130,186,467, 2026-05-26) was a PRE-FIX UNDERCOUNT: that
    #     reference predated the relPhi HasQuotientType fix and dropped genuine
    #     rank->=2 2-group-glue subdirect classes (and also carried dedup dupes).
    #     The fresh post-fix v3only build is RA-clean and validates exactly against
    #     the correct S20 reference on all 118,882 combos.  See [[s21_value_correction]].
    #     The +10.2M is concentrated in 8 [3,2]xD8 combos; an independent
    #     RepresentativeAction dedup of those combos reproduced the counts.
    19: 16745233, 20: 104994596, 21: 245393739,
}


# --- OEIS A005432 / A116693 (labelled subgroups, harvest target) ----------
# A005432: number of LABELLED subgroups of S_n (conjugates counted separately).
# Known through a(18) (OEIS).  L(n) = sum_{m=0..n} C(n,m) * L_FPF(m).
A005432 = {
    0: 1, 1: 1, 2: 2, 3: 6, 4: 30, 5: 156, 6: 1455, 7: 11300,
    8: 151221, 9: 1694723, 10: 29594446, 11: 404126228,
    12: 10594925360, 13: 175238308453, 14: 5651774693595,
    15: 117053117995400, 16: 5320744503742316,
    17: 125889331236297288, 18: 7598016157515302757,
}

# A116693: per-m labelled count of FPF subgroups of S_m (no fixed points).
# A005432 = binomial transform of A116693.  Values computed via exact inverse
# binomial transform of A005432 (verified by post-pass through m=13).
A116693 = {
    0: 1, 1: 0, 2: 1, 3: 2, 4: 15, 5: 50, 6: 874, 7: 3515,
    8: 94638, 9: 634630, 10: 18368060, 11: 149965474,
    12: 7392944314, 13: 61596293433, 14: 4042125261152,
    15: 46326163964879, 16: 4045711099761347,
    17: 47868661342996788, 18: 6066544790946772416,
}


# --- Historical wall-time baselines (per-n, fresh-build full pipeline) ----
# From fresh_s2_s21_0526.log (killed mid-n=20 on 2026-05-27, 8 workers,
# super_batch_jobs=10).  This is the most recent apples-to-apples comparison
# point; replaces the older CLAUDE.md estimates which were across different
# tuning + cache states.
TIMING_BASELINE = {
    2: 3.8, 3: 3.9, 4: 4.0, 5: 5.9, 6: 9.2, 7: 7.5,
    8: 17.6, 9: 18.2, 10: 33.4, 11: 41.1, 12: 108.5,
    13: 131.5, 14: 301.4, 15: 467.4, 16: 1439.1,
    17: 1998.0, 18: 9058.7, 19: 12502.7,
    # n=20 was still running when the orchestrator was killed; no baseline.
}


# --- Route tables ---------------------------------------------------------

# (d, t) pairs whose TransitiveGroup(d, t) is elementary abelian (= (Z/p)^m,
# d = p^m).  (2,1) excluded since c2_fast already covers it more efficiently.
# Used to route pure [(d,t)]^k combos to the b_elemab linear-algebra path.
ELEM_AB_TG = {
    (3, 1), (4, 2), (5, 1), (7, 1), (8, 3), (9, 2),
    (11, 1), (13, 1), (16, 3),
}


# (d, t) pairs the b_power pure-power engine handles directly with its own
# enumeration kernel (no towers, no ports, no fold).  Preempts bd8_fast and
# elemab_fast for pure-power combos in this set.  (2,1) excluded since
# c2_fast already covers it.  (3,2) S3 was dropped 2026-05-21: its kernel
# B2G3_SD_EnumerateClusterS3Fast lived in the deleted v3 adapter directory
# and was never tracked.  Pure S_3^k now falls through to distinguished /
# holt_split / burnside_m2 / wreath_* via the regular routing.
B_POWER_TG = {(3, 1), (4, 1), (4, 2), (4, 3)}


# --- Static env-var tunables ---------------------------------------------
#
# Resolved once at import time.  These have no dependency on argparse and
# don't change after process startup.  Anything more dynamic lives in the
# scheduler.

def _env_flag(name: str) -> bool:
    return os.environ.get(name) == "1"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Forces wreath_ra route on single-cluster m>=3 combos regardless of total_n.
FORCE_WREATH_RA = _env_flag("BUILD_SN_FORCE_WREATH_RA")

# Forces wreath_via_2factor route on single-cluster m>=3 combos regardless
# of total_n.
FORCE_WREATH_2F = _env_flag("BUILD_SN_FORCE_WREATH_2F")

# Threshold (total_n) at or above which single-cluster m>=3 combos route to
# wreath_via_2factor instead of wreath_ra.
WREATH_2F_MIN_N = _env_int("BUILD_SN_WREATH_2F_MIN_N", 16)

# Disables the b_power pure-power engine; pure-power combos in B_POWER_TG
# fall through to their previous routes (bd8_fast / elemab_fast /
# distinguished / holt_split / burnside_m2 / wreath_*).  Used by the parity
# script to compare new vs old dispatcher output.
DISABLE_B_POWER = _env_flag("BUILD_SN_DISABLE_B_POWER")

# BUILD_SN_C2GLUE=0 disables the c2_glue streaming route (combos with exactly
# one (2,1) block -> run_c2_glue_path.py: glue forced to {1,C2}, entry-local
# Goursat, NO LEFT H-cache).  Disabled combos fall back to their previous
# route (distinguished).  Default ON — landed 2026-06-09, validated 841/841
# vs v3only n=5..13 incl. class_sum; ~17.5x on n=18 [2,1]_[4,3]^4.
DISABLE_C2_GLUE = os.environ.get("BUILD_SN_C2GLUE") == "0"

# BUILD_SN_C2GLUE2=0 disables the C2^2-glue streaming route (combos with
# exactly TWO (2,1) blocks + a non-degree-2 cluster, the peel_c2_pair family
# -> run_c2_glue2_path.py: glue {1, C2, V4}, block-swap Aut collapse
# hand-derived, entry-local Goursat, NO LEFT H-cache, --shards line-range
# fan-out).  Disabled combos fall back to their previous route
# (peel_c2_pair).  Default ON — landed 2026-06-11, validated 2518/2518 exact
# (deduped + class_sum) vs fresh_0604 n=8..17.
DISABLE_C2_GLUE2 = os.environ.get("BUILD_SN_C2GLUE2") == "0"

# BUILD_SN_C3GLUE=0 disables the c3_glue streaming route (combos with exactly
# one degree-3 block against a 3-coprime LEFT -> run_c2_glue_path.py, which
# already implements (3,1)/(3,2) RIGHTs: glue forced to {1} (C3) or {1, C2}
# (S3, kernel A3 characteristic), entry-local Goursat, NO LEFT H-cache; the
# engine re-checks coprimality GAP-side and reports RESULT_NA otherwise).
# Disabled combos fall back to their previous route (distinguished /
# holt_split).  Every FPF class surjects onto each block constituent, so
# "no LEFT species order divisible by 3" is an EXACT test for 3 coprime to
# |H_L| — checked Python-side via TG_ORDERS_PATH.
DISABLE_C3_GLUE = os.environ.get("BUILD_SN_C3GLUE") == "0"

# BUILD_SN_IDENTITY=0 disables the identity routes (id_product / id_absorb /
# id_transfer -> run_identity_path.py: coprime-cluster product, single-block
# absorption, and D_2d/S_d -> (2,1) transfer — pure-Python textual
# materialization from already-built lower-n files, NO GAP).  All three
# identities verified exact (deduped + labelled, 0 failures) against every
# applicable s2..s22 combo (2026-07-02, memory
# `coprime_product_transfer_identities`).  Disabled combos fall back to
# their previous route (c2_glue / c3_glue / distinguished / ...).
DISABLE_IDENTITY = os.environ.get("BUILD_SN_IDENTITY") == "0"

# Size(TransitiveGroup(d,t)) for d=2..22, generated 2026-07-02 by
# _gen_tg_orders.py (one-shot GAP run).  Loaded lazily by runner.route for
# the c3_glue 3-coprime species check.
TG_ORDERS_PATH = ROOT / "database" / "tg_orders.json"
