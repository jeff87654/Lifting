#!/usr/bin/env python3
"""run_b_d8_path.py - invoke b_d8.g for pure [4,3]^k combos
(T(4,3) = D_8, the dihedral group of order 8 acting transitively on 4 points).

Uses Frattini-factor enumeration: each subgroup H <= D_8^k corresponds to a
triple (U, C, ell) where U = HZ/Z <= F_2^{2k} (Q-component, mod center),
C = H n Z <= F_2^k (Z-component) with q(U) subset C, and ell is a residue class
in Hom(U, Z/C)/R. Orbits taken under (D_8 wr S_k)-conjugacy.

Usage:
    python run_b_d8_path.py --combo "[4,3]_[4,3]_[4,3]_[4,3]_[4,3]" \\
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
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_b_d8")))
TMP_DIR.mkdir(parents=True, exist_ok=True)


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo(combo_str: str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple((int(d), int(t)) for d, t in pairs)


def run_bd8(combo_str: str, output_path, timeout: int = 86400) -> dict:
    t0 = time.time()
    combo = parse_combo(combo_str)
    if not combo:
        return {"error": "empty combo"}
    if not all(pair == (4, 3) for pair in combo):
        return {"error": "not pure [4,3]^k"}
    k = len(combo)

    work = TMP_DIR / f"b_d8_k{k}"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "b_d8.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"

    out_cyg = str(output_path).replace("\\", "/")
    run_g.write_text(
        'LogTo("' + to_cyg(log) + '");\n'
        'Read("C:/Users/jeffr/Downloads/Lifting/b_d8.g");\n'
        f'total := WriteBD8File({k}, "{out_cyg}");\n'
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
        return {"error": "b_d8: no RESULT",
                "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    total = int(m.group(1))
    return {
        "combo": "_".join(f"[{d_},{t_}]" for d_, t_ in combo),
        "mode": "b_d8",
        "predicted": total,
        "candidates": total,
        "elapsed_s": elapsed,
        "output_path": str(output_path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--timeout", type=int, default=86400)
    args = ap.parse_args()
    result = run_bd8(args.combo, args.output_path, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
