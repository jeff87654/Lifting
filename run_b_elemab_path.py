#!/usr/bin/env python3
"""run_b_elemab_path.py - invoke b_elemab.g for pure [(d,t)]^k combos
where T(d,t) is elementary abelian (T = (Z/p)^m, d = p^m, abelian).

Validated for (p,m) in {(3,1), (5,1), (2,2)} against parallel_sn_topt_v3
ground truth on 11 cases. Extends b21's approach from (p=2, m=1) to general
elementary abelian factors via GL_m(F_p) wr S_k orbit enumeration.

Usage:
    python run_b_elemab_path.py --combo "[4,2]_[4,2]_[4,2]_[4,2]_[4,2]" \\
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
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_b_elemab")))
TMP_DIR.mkdir(parents=True, exist_ok=True)


# Map (d, t) -> (p, m) for elementary abelian transitive groups (T = (Z/p)^m).
# Verified via GAP IsAbelian + AbelianInvariants. (2,1) is excluded here since
# the existing c2_fast path (with hardcoded reps for k<=6 and b21 for k>=7)
# is faster.
ELEM_AB_TG = {
    (3, 1): (3, 1),     # C_3
    (4, 2): (2, 2),     # V_4 = C_2^2
    (5, 1): (5, 1),     # C_5
    (7, 1): (7, 1),     # C_7
    (8, 3): (2, 3),     # C_2^3
    (9, 2): (3, 2),     # C_3^2
    (11, 1): (11, 1),   # C_11
    (13, 1): (13, 1),   # C_13
    (16, 3): (2, 4),    # C_2^4
}


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo(combo_str: str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple((int(d), int(t)) for d, t in pairs)


def run_elemab(combo_str: str, output_path, timeout: int = 3600) -> dict:
    t0 = time.time()
    combo = parse_combo(combo_str)
    if not combo:
        return {"error": "empty combo"}
    if not all(pair == combo[0] for pair in combo):
        return {"error": "not pure"}
    d, t = combo[0]
    if (d, t) not in ELEM_AB_TG:
        return {"error": f"({d},{t}) not in elem-ab table"}
    p, m = ELEM_AB_TG[(d, t)]
    k = len(combo)

    work = TMP_DIR / f"b_elemab_d{d}_t{t}_k{k}"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "b_elemab.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"

    out_cyg = str(output_path).replace("\\", "/")
    run_g.write_text(
        'LogTo("' + to_cyg(log) + '");\n'
        'Read("C:/Users/jeffr/Downloads/Lifting/b_elemab.g");\n'
        f'total := WriteBElemabFile({p}, {m}, {k}, {d}, {t}, "{out_cyg}");\n'
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
        return {"error": "b_elemab: no RESULT",
                "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    total = int(m.group(1))
    return {
        "combo": "_".join(f"[{d_},{t_}]" for d_, t_ in combo),
        "mode": "b_elemab",
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
    result = run_elemab(args.combo, args.output_path, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
