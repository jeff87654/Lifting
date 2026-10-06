#!/usr/bin/env python3
"""wreath_ra_dedup.py — discoverability alias for the wreath_ra RA-dedup engine.

THE REAL IMPLEMENTATION LIVES IN ``predict_full_general_wreath.py``.

This thin shim exists only so that searches for "wreath_ra", "RA dedup", or
"canonical-form dedup" land on the right module.  The engine it points to is the
single-cluster ``[d,t]^m`` predictor that:

  * materializes the FPF subdirect subgroups of the combo,
  * buckets them by a W-invariant fingerprint (``fp_fingerprint`` /
    ``fp_fingerprint_rich`` + the Tier-A ``PHI_*`` gluing code / Tier-D-lite
    ``canonPhi`` canonical form), then
  * resolves each bucket by pairwise ``RepresentativeAction(W, H_i, H_j)`` under
    union-find (``UF_Find`` / ``UF_Union``), where ``W = N_T wr S_m``.

It is also the project's dedup *testing workhorse*: ``--candidates-from`` dedups
candidate sets emitted by other engines.

Routing (``runner/route.py`` ``_resolve_wreath``) still dispatches to
``predict_full_general_wreath.py`` by its original name — this alias is import /
CLI sugar only.

Usage (identical to the real module)::

    python wreath_ra_dedup.py --combo "[4,2]_[4,2]_[4,2]" --target-n 12
"""
from __future__ import annotations

# Re-export the public surface so `from wreath_ra_dedup import predict_wreath`
# works exactly like importing from the real module.
from predict_full_general_wreath import (  # noqa: F401
    predict_wreath,
    main,
    GAP_WREATH,
    parse_combo_file,
)

if __name__ == "__main__":
    main()
