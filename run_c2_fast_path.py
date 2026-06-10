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
import math
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


# Pure [2,1]^m is just full-support binary linear codes of length m,
# modulo coordinate permutation.  These representatives are row bases encoded
# as bit masks on the m C2 coordinates.  The table covers the slow low-degree
# cases in S4..S12 without starting GAP.
ALL_C2_CODE_REPS = {
    1: [[1]],
    2: [[3], [1, 2]],
    3: [[7], [5, 2], [5, 6], [1, 2, 4]],
    4: [[15], [5, 10], [13, 2], [13, 10], [9, 2, 4],
        [9, 10, 4], [9, 10, 12], [1, 2, 4, 8]],
    5: [[31], [13, 18], [21, 26], [29, 2], [29, 18],
        [9, 18, 4], [9, 18, 20], [25, 2, 4], [25, 10, 20],
        [25, 18, 4], [25, 18, 20], [17, 2, 4, 8],
        [17, 18, 4, 8], [17, 18, 20, 8], [17, 18, 20, 24],
        [1, 2, 4, 8, 16]],
    6: [[63], [13, 50], [29, 34], [45, 50], [53, 58], [61, 2],
        [61, 34], [9, 18, 36], [25, 34, 4], [25, 34, 36],
        [25, 42, 52], [25, 50, 36], [41, 18, 36], [41, 50, 4],
        [41, 50, 36], [57, 2, 4], [57, 18, 36], [57, 34, 4],
        [57, 34, 36], [17, 18, 36, 40], [17, 34, 4, 8],
        [17, 34, 36, 8], [17, 34, 36, 40], [49, 2, 4, 8],
        [49, 18, 36, 8], [49, 18, 36, 40], [49, 34, 4, 8],
        [49, 34, 36, 8], [49, 34, 36, 40], [49, 50, 20, 40],
        [33, 2, 4, 8, 16], [33, 34, 4, 8, 16],
        [33, 34, 36, 8, 16], [33, 34, 36, 40, 16],
        [33, 34, 36, 40, 48], [1, 2, 4, 8, 16, 32]],
}


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo(combo_str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def _mask_to_perm(mask: int, m: int) -> str:
    cycles = []
    for i in range(m):
        if (mask >> i) & 1:
            cycles.append(f"({2*i+1},{2*i+2})")
    return "".join(cycles) if cycles else "()"


def _c2_labelled_class_sum(k: int) -> int:
    """Labelled `# class_sum` (A005432 / A116693 contribution) for pure
    [2,1]^k — the orbit type [2^k] in S_{2k}.

    Lets this fast path emit the labelled count inline like the harvest-
    instrumented engine, so labelled_postpass.py takes its inline fast path
    and skips the per-rep Normalizer-in-W harvest (which was the slow step
    for k=10).

    Closed form: each rep is a full-support binary code V <= F_2^k, and
    (b_elemab_harvest.g) cs = (2k)! / (2^k * |Stab_{S_k}(V)|).  Summing over
    S_k-orbit reps collapses (orbit-stabilizer) to

        class_sum(k) = (2k-1)!! * A(k)

    with A(k) = number of full-support (no zero coordinate) subspaces of
    F_2^k = sum_{j=0}^{k} (-1)^(k-j) C(k,j) G(j), where G = Galois numbers
    (G(n) = number of subspaces of F_2^n, OEIS A006116).

    Verified == BElemab_ClassSumWithSizes(2,1,k).class_sum for k=1..9
    (1, 6, 90, 2730, 149310, 13825350, 2082970890, 497792745450,
     185490329374350); k=10 = 106525008449209350.
    """
    # Galois numbers G(0..k):  G(n+1) = 2 G(n) + (2^n - 1) G(n-1).
    G = [1, 2]
    while len(G) <= k:
        n = len(G) - 1
        G.append(2 * G[n] + (2 ** n - 1) * G[n - 1])
    A = sum((-1) ** (k - j) * math.comb(k, j) * G[j] for j in range(k + 1))
    dfact = 1                       # (2k-1)!!
    for i in range(1, 2 * k, 2):
        dfact *= i
    return dfact * A


def _insert_class_sum_header(output_path, class_sum: int) -> None:
    """Splice a `# class_sum: N` line into an already-written combo file
    (after the `# deduped:` header) if not already present.  Used for the
    b21 path, where GAP writes the file."""
    out = Path(output_path)
    try:
        text = out.read_text(encoding="utf-8")
    except OSError:
        return
    if re.search(r"^# class_sum:", text, re.MULTILINE):
        return
    lines, new_lines, inserted = text.split("\n"), [], False
    for ln in lines:
        new_lines.append(ln)
        if not inserted and ln.startswith("# deduped:"):
            new_lines.append(f"# class_sum: {class_sum}")
            inserted = True
    if not inserted:
        new_lines.insert(0, f"# class_sum: {class_sum}")
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(new_lines))


def _write_all_c2_binary_code_reps(combo, output_path, elapsed_ms=0):
    m = len(combo)
    reps = ALL_C2_CODE_REPS[m]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    combo_header = "[ " + ", ".join("[ 2, 1 ]" for _ in range(m)) + " ]"
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        class_sum = _c2_labelled_class_sum(m)
        f.write(f"# combo: {combo_header}\n")
        f.write(f"# candidates: {len(reps)}\n")
        f.write(f"# deduped: {len(reps)}\n")
        f.write(f"# class_sum: {class_sum}\n")
        f.write(f"# elapsed_ms: {elapsed_ms}\n")
        for basis in reps:
            gens = ",".join(_mask_to_perm(mask, m) for mask in basis)
            f.write(f"[{gens}]\n")
    tmp.replace(out)
    return {
        "combo": "_".join("[2,1]" for _ in range(m)),
        "mode": "c2_binary_code_reps",
        "predicted": len(reps),
        "candidates": len(reps),
        "class_sum": class_sum,
        "elapsed_s": round(elapsed_ms / 1000.0, 3),
        "output_path": str(output_path),
    }


def _run_b21(combo, output_path, timeout=3600):
    """Pure [2,1]^k via b21_writer_final.g (linear-algebra enumerator).

    Uses support-first GL_r orbits + GUAVA `IsEquivalent` for collision
    resolution.  For k=7..10 the totals are 80, 194, 506, 1449 (matches
    OEIS A006741).  Mathematically equivalent to enumerating nondegenerate
    [k,r]_2 binary linear codes up to permutation equivalence.
    """
    t0 = time.time()
    k = len(combo)
    work = TMP_DIR / f"b21_k{k}"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "b21.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"

    out_cyg = str(output_path).replace("\\", "/")
    run_g.write_text(
        'LogTo("' + to_cyg(log) + '");\n'
        'Read("C:/Users/jeffr/Downloads/Lifting/b21_writer_final.g");\n'
        f'total := WriteB21File({k}, "{out_cyg}");\n'
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
        return {"error": "b21 timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)

    log_text = (
        log.read_text(encoding="utf-8", errors="ignore")
        if log.exists() else ""
    )
    m = re.search(r"RESULT predicted=\s*(\d+)", log_text)
    if not m:
        return {"error": "b21: no RESULT",
                "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    total = int(m.group(1))
    # Emit the labelled # class_sum inline (closed form; GAP wrote the file,
    # so splice the header in) -> labelled_postpass takes its inline fast path
    # and skips the slow per-rep Normalizer-in-W harvest for this combo.
    class_sum = _c2_labelled_class_sum(k)
    _insert_class_sum_header(output_path, class_sum)
    return {
        "combo": "_".join("[2,1]" for _ in range(k)),
        "mode": "b21_linear_algebra",
        "predicted": total,
        "candidates": total,
        "class_sum": class_sum,
        "elapsed_s": elapsed,
        "output_path": str(output_path),
    }


def run_c2(combo_str, output_path, timeout=3600):
    t0 = time.time()
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

    if all(pair == (2, 1) for pair in combo):
        if len(combo) in ALL_C2_CODE_REPS:
            elapsed_ms = int(round((time.time() - t0) * 1000))
            return _write_all_c2_binary_code_reps(combo, output_path, elapsed_ms)
        # Pure [2,1]^k with k not in the hardcoded table -> b21
        # linear-algebra enumerator (support-first GL_r orbits + GUAVA
        # IsEquivalent collision resolve).  Validated for k=2..9 against
        # OEIS A006741; k=10 produces 1449 classes verified pairwise
        # non-conjugate in S_20 and W (2026-05-13).
        return _run_b21(combo, output_path, timeout=timeout)

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
