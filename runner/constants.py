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
}


# --- Route tables ---------------------------------------------------------

# (d, t) pairs whose TransitiveGroup(d, t) is elementary abelian (= (Z/p)^m,
# d = p^m).  (2,1) excluded since c2_fast already covers it more efficiently.
# Used to route pure [(d,t)]^k combos to the b_elemab linear-algebra path.
ELEM_AB_TG = {
    (3, 1), (4, 2), (5, 1), (7, 1), (8, 3), (9, 2),
    (11, 1), (13, 1), (16, 3),
}


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
