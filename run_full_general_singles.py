#!/usr/bin/env python3
"""Run predict_full_general.py on the 19 single-cluster m>=3 NON_PREDICTABLE
combos (partitions [6,6,6], [3,3,3,3,3,3], [2,1]^9) and compare predictions
against stored actuals."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
data = json.load(open(ROOT / "predict_species_tmp" / "18" / "_compare_report.json"))

target_partitions = {"[6,6,6]", "[3,3,3,3,3,3]", "[2,2,2,2,2,2,2,2,2]"}
single = [r for r in data["rows"] if r["status"] == "NON_PREDICTABLE"
          and r["partition"] in target_partitions]
single.sort(key=lambda r: r.get("actual") or 0)
print(f"Running predict_full_general.py on {len(single)} single-cluster combos\n")

n_match = n_diff = n_err = 0
diffs = []
for idx, r in enumerate(single, 1):
    combo_str = r["combo"]
    actual = r.get("actual")
    pairs = re.findall(r"\[(\d+),(\d+)\]", combo_str)
    d, t = pairs[0]
    print(f"[{idx}/{len(single)}] {r['partition']} {combo_str}"
          f" (actual={actual})... ", end="", flush=True)
    t0 = time.time()
    cmd = [sys.executable, "predict_full_general.py",
           "--combo", combo_str, "--dt", f"{d},{t}",
           "--target-n", "18", "--timeout", "1800"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2000)
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT ({time.time()-t0:.0f}s)")
        n_err += 1
        continue
    elapsed = time.time() - t0
    out = proc.stdout
    m = re.search(r'"predicted":\s*(\d+)', out)
    if not m:
        print(f"ERROR ({elapsed:.0f}s)")
        print(out[-500:])
        n_err += 1
        continue
    pred = int(m.group(1))
    if pred == actual:
        print(f"MATCH pred={pred} ({elapsed:.0f}s)")
        n_match += 1
    else:
        delta = pred - (actual or 0)
        print(f"DIFF pred={pred} actual={actual} delta={delta:+} ({elapsed:.0f}s)")
        n_diff += 1
        diffs.append((combo_str, actual, pred))

print(f"\n=== Summary: match={n_match} diff={n_diff} error={n_err} ===")
if diffs:
    print("Discrepancies:")
    for c, a, p in diffs:
        print(f"  {c}: actual={a} pred={p}")
