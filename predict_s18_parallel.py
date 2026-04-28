#!/usr/bin/env python3
"""
predict_s18_parallel.py — run predict_s18_species.py across many S18 partitions
in parallel.

Each worker invokes:
    python predict_s18_species.py --target 18 --partition <P> --batch [flags]

Partitions are processed independently (each holds its own GAP subprocess and
writes to predict_species_tmp/18/). Default concurrency = 4. Pass --workers N
to change.

Usage:
    python predict_s18_parallel.py --workers 8 --cheapest-only
    python predict_s18_parallel.py --partition "[10,8]" --partition "[10,4,4]"
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
S18_DIR = ROOT / "parallel_s18"
SCRIPT = ROOT / "predict_s18_species.py"
LOG_DIR = ROOT / "predict_species_tmp" / "_parallel_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def list_s18_partitions() -> list[str]:
    out = []
    for d in sorted(S18_DIR.iterdir()):
        if not d.is_dir():
            continue
        if "backup" in d.name.lower() or d.name.startswith("_"):
            continue
        if not (d.name.startswith("[") and d.name.endswith("]")):
            continue
        out.append(d.name)
    return out


def estimate_cost(partition: str) -> int:
    """Cheap heuristic: count of .g files in the S18 partition dir."""
    p = S18_DIR / partition
    if not p.is_dir():
        return 1
    return sum(1 for f in p.iterdir() if f.is_file() and f.suffix == ".g")


def run_one(partition: str, cheapest_only: bool, force: bool, timeout: int | None) -> dict:
    log = LOG_DIR / f"{partition}.log"
    cmd = [sys.executable, str(SCRIPT), "--target", "18", "--partition", partition, "--batch"]
    if cheapest_only:
        cmd.append("--cheapest-only")
    if force:
        cmd.append("--force")
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    t0 = time.time()
    try:
        with open(log, "w", encoding="utf-8") as f:
            f.write(f"$ {' '.join(cmd)}\n\n")
            f.flush()
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        rc = proc.returncode
        err = None
    except subprocess.TimeoutExpired:
        rc = -1
        err = "timeout"
    except Exception as e:
        rc = -2
        err = str(e)
    return {"partition": partition, "rc": rc, "err": err,
            "elapsed_s": round(time.time() - t0, 1), "log": str(log)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--partition", action="append", default=[],
                    help="Restrict to these partitions (repeatable). Default: all.")
    ap.add_argument("--cheapest-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Per-partition wall-clock timeout (seconds).")
    ap.add_argument("--skip-larger-than", type=int, default=None,
                    help="Skip partitions whose .g file count exceeds this.")
    args = ap.parse_args()

    parts = args.partition or list_s18_partitions()

    if args.skip_larger_than is not None:
        parts = [p for p in parts if estimate_cost(p) <= args.skip_larger_than]

    # Largest first → better load balance.
    parts.sort(key=estimate_cost, reverse=True)

    print(f"Running {len(parts)} partitions with {args.workers} workers")
    for p in parts[:8]:
        print(f"  {p:<22} {estimate_cost(p):>5} combos")
    if len(parts) > 8:
        print(f"  ... and {len(parts)-8} more")

    results = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, p, args.cheapest_only, args.force, args.timeout): p for p in parts}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done = len(results)
            elapsed = time.time() - t0
            print(f"[{done}/{len(parts)}] {r['partition']:<22} rc={r['rc']:>3} "
                  f"elapsed={r['elapsed_s']:.0f}s  total_wall={elapsed:.0f}s  err={r['err']}")

    out = LOG_DIR / "_parallel_summary.json"
    out.write_text(json.dumps({
        "total_wall_s": round(time.time() - t0, 1),
        "n_partitions": len(parts),
        "n_ok": sum(1 for r in results if r["rc"] == 0),
        "results": results,
    }, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
