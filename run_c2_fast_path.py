#!/usr/bin/env python3
"""
run_c2_fast_path.py — invoke c2_fast_path_writer.g for a single combo and
write its result to a parallel_sn-format file.

Usage:
    python run_c2_fast_path.py --combo "[6,1]_[4,3]_[2,1]_[2,1]" \
                                --output-path /path/to/out.g
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TEMPLATE = ROOT / "c2_fast_path_writer.g"
TMP_DIR = Path(os.environ.get(
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_c2_fast")))
TMP_DIR.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo(combo_str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def run_c2(combo_str, output_path, timeout=3600):
    combo = parse_combo(combo_str)
    partition = sorted([d for d, _ in combo], reverse=True)
    # Eligibility: trailing 2's >= 2.
    n_trail = 0
    for d in reversed(partition):
        if d == 2:
            n_trail += 1
        else:
            break
    if n_trail < 2:
        return {"error": f"not C_2-eligible: trailing 2s = {n_trail}"}

    target_str = "_".join(f"[{d},{t}]" for d, t in combo)
    work = TMP_DIR / target_str
    work.mkdir(parents=True, exist_ok=True)
    log = work / "c2.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"

    partition_str = "[" + ",".join(str(d) for d in partition) + "]"
    combo_str_gap = "[" + ",".join(f"[{d},{t}]" for d, t in combo) + "]"

    template = TEMPLATE.read_text(encoding="utf-8")
    run_g.write_text(
        template
        .replace("__LOG_PATH__", to_cyg(log))
        .replace("__PARTITION_STR__", partition_str)
        .replace("__COMBO_STR__", combo_str_gap)
        .replace("__OUTPUT_PATH__", to_cyg(output_path)),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # timeout >= 30 days OR <= 0 means "no timeout" (avoid threading.Lock overflow on Windows).
    sub_timeout = None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30) else timeout
    try:
        if sub_timeout is None:
            subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)

    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    if "NOT_APPLICABLE" in log_text:
        return {"error": "C_2 path returned fail", "log_tail": log_text[-1000:]}
    m = re.search(r"RESULT predicted=\s*(\d+)\s+candidates=\s*(\d+)\s+elapsed_ms=\s*(\d+)",
                  log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:], "elapsed_s": elapsed}
    return {
        "combo": target_str,
        "mode": "c2_fast_path",
        "predicted": int(m.group(1)),
        "candidates": int(m.group(2)),
        "elapsed_s": elapsed,
        "output_path": str(output_path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    result = run_c2(args.combo, args.output_path, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
