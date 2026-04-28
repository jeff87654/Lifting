"""rerun_s18_missing.py — focused rerun for the 31 missing S18 combos.

Each combo runs predict_2factor.py directly (no super-batching) with no
timeout. ProcessPoolExecutor with --workers (default 8) spawns one GAP per
combo concurrently. Skips combos whose output file already exists.

Usage:
    python rerun_s18_missing.py                # 8 workers, no timeout
    python rerun_s18_missing.py --workers 4
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
SN_DIR = ROOT / "parallel_sn_v2"

# 7 still-missing S18 combos after the first rerun pass — all heavy multi-[4,3]
# LEFTs that needed [4,3]^4-class H-cache builds.  Will exercise the new
# q-size-filtered cache path (M_R=2 means LEFT cache is computed only for
# Q-sizes {1, 2}).
MISSING = [
    ((4, 4, 4, 4, 2), "[2,1]_[4,2]_[4,3]_[4,3]_[4,3]"),
    ((4, 4, 4, 4, 2), "[2,1]_[4,3]_[4,3]_[4,3]_[4,3]"),
]


def part_dirname(partition):
    return "[" + ",".join(str(d) for d in partition) + "]"


def parse_combo(combo_str):
    """[2,1]_[4,3]_[4,3] -> [(2,1), (4,3), (4,3)]"""
    parts = combo_str.split("_")
    return [tuple(int(x) for x in p[1:-1].split(",")) for p in parts]


def determine_mode(combo_tuple):
    """Mirror build_sn_v2.route() for non-bootstrap, non-c2_fast combos.
    None of the 31 missing combos are pure C_2^n, so c2_fast does not apply."""
    clusters = Counter(combo_tuple)
    if any(mult == 1 for mult in clusters.values()):
        return "distinguished"
    if len(clusters) >= 2:
        return "holt_split"
    only_mult = next(iter(clusters.values()))
    if only_mult == 2:
        return "burnside_m2"
    return "wreath_ra"


def run_one(part_combo):
    partition, combo_str = part_combo
    output_path = SN_DIR / "18" / part_dirname(partition) / f"{combo_str}.g"
    if output_path.exists():
        return (combo_str, "already_present", 0.0, "")

    combo_tuple = parse_combo(combo_str)
    mode = determine_mode(combo_tuple)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "wreath_ra":
        script = "predict_full_general_wreath.py"
        extra = ["--target-n", "18"]
    else:
        script = "predict_2factor.py"
        extra = ["--mode", mode, "--force"]

    cmd = [sys.executable, str(ROOT / script),
           "--combo", combo_str,
           "--output-path", str(output_path),
           "--timeout", "0"] + extra

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=None)
    except Exception as e:
        return (combo_str, f"exception: {type(e).__name__}", time.time() - t0, str(e)[:300])
    elapsed = time.time() - t0
    if proc.returncode != 0:
        return (combo_str, f"rc={proc.returncode}", elapsed,
                (proc.stderr[-300:] or proc.stdout[-300:]))
    if not output_path.exists():
        return (combo_str, "no_output", elapsed, proc.stdout[-300:])
    return (combo_str, "ok", elapsed, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    todo = [pc for pc in MISSING
            if not (SN_DIR / "18" / part_dirname(pc[0]) / f"{pc[1]}.g").exists()]

    print(f"=== rerun_s18_missing: {len(todo)} of {len(MISSING)} combos to run "
          f"({args.workers} workers, no timeout) ===\n", flush=True)

    t_start = time.time()
    n_done = 0
    n_ok = 0
    n_err = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, pc): pc for pc in todo}
        for fut in as_completed(futures):
            partition, combo_str = futures[fut]
            try:
                _, status, elapsed, err = fut.result()
            except Exception as e:
                status = "future-exception"
                elapsed = 0.0
                err = str(e)
            n_done += 1
            tag = "OK " if status == "ok" else "ERR"
            if status == "ok":
                n_ok += 1
            else:
                n_err += 1
            ts = time.time() - t_start
            print(f"[{n_done}/{len(todo)} t+{ts:6.0f}s] {tag} "
                  f"{part_dirname(partition)}/{combo_str}  ({elapsed:.0f}s) {status}",
                  flush=True)
            if err:
                err_clean = err.strip().replace("\n", " | ")[:250]
                print(f"      {err_clean}", flush=True)

    print(f"\n=== done in {time.time() - t_start:.0f}s — ok={n_ok} err={n_err} ===")


if __name__ == "__main__":
    main()
