#!/usr/bin/env python3
"""run_b_power_path.py - invoke b_power/power_dispatch.g for a pure power
TG(d,t)^k combo and write the legacy combo-file at --output-path.

Supports (d,t) in {(3,1) C3, (3,2) S3, (4,1) C4, (4,2) V4, (4,3) D8}.
Pure C2 is out of scope (use run_c2_fast_path.py).

Usage:
    python run_b_power_path.py --combo "[3,2]_[3,2]_[3,2]" \\
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
GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
TMP_DIR = Path(os.environ.get(
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_b_power")))
TMP_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_TG = {(3, 1), (3, 2), (4, 1), (4, 2), (4, 3)}


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo(combo_str: str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple((int(d), int(t)) for d, t in pairs)


def run_b_power(combo_str: str, output_path, timeout: int = 3600) -> dict:
    t0 = time.time()
    combo = parse_combo(combo_str)
    if not combo:
        return {"error": "empty combo"}
    if len(combo) < 2:
        return {"error": "b_power requires k >= 2"}
    if not all(pair == combo[0] for pair in combo):
        return {"error": "not pure"}
    d, t = combo[0]
    if (d, t) not in SUPPORTED_TG:
        return {"error": f"({d},{t}) not in b_power supported TGs"}
    k = len(combo)

    work = TMP_DIR / f"b_power_d{d}_t{t}_k{k}"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "b_power.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"

    # GAP streams the combo file headers-first and non-atomically; write to
    # a .tmp sibling and publish only after RESULT confirms completion, so a
    # killed job can never leave a truncated file at the canonical path
    # (glue/2-factor engines at higher n stream these files as sources).
    out_final = Path(output_path)
    out_tmp = out_final.with_suffix(out_final.suffix + ".tmp")
    if out_tmp.exists():
        out_tmp.unlink()
    out_cyg = str(out_tmp).replace("\\", "/")
    run_g.write_text(
        'LogTo("' + to_cyg(log) + '");\n'
        'Read("C:/Users/jeffr/Downloads/Lifting/b_power/power_dispatch.g");\n'
        f'total := B2GPowerRun({d}, {t}, {k}, "emit", "{out_cyg}");\n'
        'Print("RESULT predicted=", total, "\\n");\n'
        'LogTo();\n'
        'QUIT;\n',
        encoding="utf-8",
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = (
        r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    )
    env["CYGWIN"] = "nodosfilewarning"
    sub_timeout = (
        None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30)
        else timeout
    )
    try:
        if sub_timeout is None:
            subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            subprocess.run(cmd, env=env, capture_output=True, text=True,
                           timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}

    elapsed = round(time.time() - t0, 1)
    log_text = (
        log.read_text(encoding="utf-8", errors="ignore")
        if log.exists() else ""
    )
    m = re.search(r"RESULT predicted=\s*(\d+)", log_text)
    if not m:
        return {"error": "b_power: no RESULT",
                "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    total = int(m.group(1))
    if not out_tmp.exists():
        return {"error": f"b_power: RESULT but no output written: {out_tmp}",
                "elapsed_s": elapsed}
    out_final.parent.mkdir(parents=True, exist_ok=True)
    out_tmp.replace(out_final)
    return {
        "combo": "_".join(f"[{d_},{t_}]" for d_, t_ in combo),
        "mode": "b_power",
        "predicted": total,
        "candidates": total,
        "elapsed_s": elapsed,
        "output_path": str(output_path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    result = run_b_power(args.combo, args.output_path, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
