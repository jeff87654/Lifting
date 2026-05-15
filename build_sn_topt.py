#!/usr/bin/env python3
"""build_sn_topt.py — entry point for the S_n FPF subgroup build orchestrator.

The runner is split across `runner/` modules; this file just calls into
`runner.scheduler.main`.

Routing per combo c (with partition λ = sorted desc {d : (d,t) in c}):
  - len(c) == 1  -> bootstrap (write GeneratorsOfGroup(TransitiveGroup(d,t)))
  - λ has ≥2 trailing 2s -> try C_2 fast path; fall through on `fail`
  - distinguished species (mult=1) -> predict_2factor --mode distinguished
  - ≥2 distinct species clusters -> predict_2factor --mode holt_split
  - m=2 single-cluster -> predict_2factor --mode burnside_m2
  - m≥3 single-cluster -> predict_full_general_wreath (small n) or the
    two-step wreath_via_2factor pipeline (n >= BUILD_SN_WREATH_2F_MIN_N).

See `runner/__init__.py` for the module layout and `runner/scheduler.py`
for the main loop.
"""
from runner.scheduler import main


if __name__ == "__main__":
    main()
