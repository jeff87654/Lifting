#!/usr/bin/env python3
"""run_wreath_via_2factor.py — wrapper for the two-step wreath dispatch.

Step 1: predict_2factor_topt.py --mode holt_split --emit-generators
        (qfree3/H_CACHE-optimized candidate generation; output is
        W_LEFT x W_RIGHT-deduped, may over-count under the full block-wreath
        ambient by C(m, a) where (a, b) is the chosen split).

Step 2: predict_full_general_wreath.py --candidates-from <fps.g>
        (bucket by block-aware fingerprints, then pairwise RA-in-W where
        W = N_T wr S_m; produces correctly S_n-deduped output and writes
        the legacy-format combo file at --output-path).

The wrapper exists so the build_sn_topt.py parallel dispatch (which expects
one subprocess command per task) can launch this single pipeline.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--target-n", type=int, required=True)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--timeout", type=int, default=3600,
                    help="per-step timeout in seconds (0 = unlimited)")
    args = ap.parse_args()

    t0 = time.time()
    out = {"route": "wreath_via_2factor", "combo": args.combo}

    step1_cmd = [sys.executable, str(ROOT / "predict_2factor_topt.py"),
                 "--combo", args.combo,
                 "--mode", "holt_split",
                 "--emit-generators",
                 "--force",
                 "--timeout", str(args.timeout)]
    s1_timeout = None if args.timeout <= 0 else args.timeout + 60
    try:
        proc1 = subprocess.run(step1_cmd, capture_output=True, text=True,
                                timeout=s1_timeout)
    except subprocess.TimeoutExpired:
        out["error"] = {"step": 1, "msg": "timeout"}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    if proc1.returncode != 0:
        out["error"] = {"step": 1, "rc": proc1.returncode,
                        "stderr": proc1.stderr[-1000:],
                        "stdout": proc1.stdout[-1000:]}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    try:
        result1 = json.loads(proc1.stdout)
    except json.JSONDecodeError:
        out["error"] = {"step": 1, "msg": "json parse",
                        "stdout": proc1.stdout[-1000:],
                        "stderr": proc1.stderr[-1000:]}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    fps_g = result1.get("generators_file")
    if not fps_g or not Path(fps_g).exists():
        out["error"] = {"step": 1, "msg": "no generators_file",
                        "result": result1}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    out["step1_orbits"] = result1.get("orbits")
    out["step1_predicted_pre_dedup"] = result1.get("predicted")
    out["step1_elapsed_s"] = result1.get("elapsed_s")
    out["fps_g"] = fps_g

    step2_cmd = [sys.executable, str(ROOT / "predict_full_general_wreath.py"),
                 "--combo", args.combo,
                 "--target-n", str(args.target_n),
                 "--candidates-from", fps_g,
                 "--output-path", args.output_path,
                 "--timeout", str(args.timeout)]
    s2_timeout = None if args.timeout <= 0 else args.timeout + 60
    try:
        proc2 = subprocess.run(step2_cmd, capture_output=True, text=True,
                                timeout=s2_timeout)
    except subprocess.TimeoutExpired:
        out["error"] = {"step": 2, "msg": "timeout"}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    if proc2.returncode != 0:
        out["error"] = {"step": 2, "rc": proc2.returncode,
                        "stderr": proc2.stderr[-1000:],
                        "stdout": proc2.stdout[-1000:]}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    try:
        result2 = json.loads(proc2.stdout)
    except json.JSONDecodeError:
        out["error"] = {"step": 2, "msg": "json parse",
                        "stdout": proc2.stdout[-1000:],
                        "stderr": proc2.stderr[-1000:]}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)
    if "error" in result2:
        out["error"] = {"step": 2, "result": result2}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)

    # Candidate-count cross-check: step 2 must have RA-deduped EXACTLY the
    # candidate set step 1 predicted.  A short fps.g (e.g. generator lines lost
    # to the single-combo driver's buffered-stream checkpoint after an unplanned
    # kill) would otherwise produce a self-consistent but UNDERCOUNTED output
    # that no downstream completeness check can detect.  On mismatch, remove the
    # output AND the stale step-1 work files so the orchestrator's retry
    # recomputes the candidates from scratch instead of resuming the divergence.
    n_mat = result2.get("n_materialized")
    n_pred1 = result1.get("predicted")
    if n_mat is not None and n_pred1 is not None and n_mat != n_pred1:
        for stale in (Path(args.output_path), Path(fps_g),
                      Path(fps_g).parent / "state.g"):
            try:
                stale.unlink()
            except OSError:
                pass
        out["error"] = {"step": 2,
                        "msg": (f"candidate count mismatch: step1 predicted "
                                f"{n_pred1} but step2 materialized {n_mat} "
                                f"(incomplete fps.g / stale resume state?); "
                                f"output + step-1 state removed for clean retry")}
        out["elapsed_s"] = time.time() - t0
        print(json.dumps(out))
        sys.exit(1)

    out["predicted"] = result2["predicted"]
    out["n_distinct"] = result2.get("n_distinct")
    out["n_materialized"] = result2.get("n_materialized")
    out["step2_elapsed_s"] = result2.get("elapsed_s")
    out["elapsed_s"] = round(time.time() - t0, 1)
    out["output_path"] = args.output_path
    print(json.dumps(out))


if __name__ == "__main__":
    main()
