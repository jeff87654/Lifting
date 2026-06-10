#!/usr/bin/env python3
"""
run_c2_glue_path.py — streaming C2-glue engine driver.

For a distinguished combo X_[d,t] whose RIGHT block (d,t) forces the Goursat
glue quotient set down to {1, C2} — (2,1) against ANY X, or (3,1)/(3,2)
against an X with no species order divisible by 3 — the classes are
entry-local (Aut(C2) trivial: no aut-saturation, no double cosets, no
cross-pair dedup).  This driver therefore streams X's already-built output
.g file line by line through c2_glue_path_writer.g instead of building /
loading a LEFT H-cache: O(1) memory, no cache serialization, and the work
shards trivially by source-line ranges (the per-LEFT cache build is
single-worker in the general engine).

Motivation: n=22 `[2,1]_[4,3]^5` routes distinguished with a D8^5 LEFT
H-cache of ~1.6M entries — infeasible to materialize; this path sidesteps
the cache entirely.

Usage (single combo):
    python run_c2_glue_path.py --combo "[2,1]_[4,3]_[4,3]" \
        --output-path out.g --source-dir parallel_sn_v3only

Batch (one GAP session for many combos; used by the validation sweep):
    python run_c2_glue_path.py --batch-json jobs.json --source-dir ...
    # jobs.json: [{"combo": "...", "output_path": "..."}, ...]
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
TEMPLATE = ROOT / "c2_glue_path_writer.g"
TMP_DIR = Path(os.environ.get(
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_c2_glue")))

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

# RIGHT blocks this path supports, in preference order.  (2,1) admits any
# LEFT; (3,2)/(3,1) additionally require 3 coprime to the LEFT species
# orders (checked GAP-side, which reports RESULT_NA otherwise).
RIGHT_CANDIDATES = [(2, 1), (3, 2), (3, 1)]


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def to_gap(p) -> str:
    return str(p).replace("\\", "/")


def parse_combo(combo_str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_to_str(combo) -> str:
    return "_".join(f"[{d},{t}]" for d, t in combo)


def combo_header(combo) -> str:
    return "[ " + ", ".join(f"[ {d}, {t} ]" for d, t in combo) + " ]"


def partition_dir(degrees) -> str:
    return "[" + ",".join(str(d) for d in sorted(degrees, reverse=True)) + "]"


def choose_right(combo):
    """Pick the RIGHT block: a supported (d,t) with species-multiplicity
    exactly 1 (multiplicity 1 is what makes the RIGHT block setwise fixed
    by N_{S_n}, which the fusion/labelled math relies on)."""
    for cand in RIGHT_CANDIDATES:
        if combo.count(cand) == 1:
            return cand
    return None


def build_job(combo_str, output_path, source_dir, idx=0, work=None):
    """Resolve eligibility + the LEFT source file; return a job dict or
    {"error": ...}."""
    combo = parse_combo(combo_str)
    if len(combo) < 2:
        return {"error": "single-block combo (bootstrap territory)"}
    right = choose_right(combo)
    if right is None:
        return {"error": "no supported multiplicity-1 RIGHT block "
                         "((2,1)/(3,2)/(3,1))"}
    x_combo = list(combo)
    x_combo.remove(right)
    x_combo = tuple(x_combo)
    m = sum(d for d, _ in x_combo)
    n = m + right[0]
    src = (Path(source_dir) / str(m) / partition_dir([d for d, _ in x_combo])
           / (combo_to_str(x_combo) + ".g"))
    if not src.exists():
        return {"error": f"left source not found: {src}"}
    return {
        "combo": combo,
        "combo_str": combo_to_str(combo),
        "right": right,
        "x_combo": x_combo,
        "m": m,
        "n": n,
        "src": src,
        "output_path": Path(output_path),
        "body": (work / f"body_{idx}.g") if work else None,
    }


def gap_jobs_g(jobs) -> str:
    entries = []
    for j in jobs:
        xsp = "[" + ",".join(f"[{d},{t}]" for d, t in j["x_combo"]) + "]"
        xdeg = "[" + ",".join(str(d) for d, _ in j["x_combo"]) + "]"
        entries.append(
            f'rec(combo := "{j["combo_str"]}",\n'
            f'    src := "{to_gap(j["src"])}",\n'
            f'    body := "{to_gap(j["body"])}",\n'
            f'    d := {j["right"][0]}, t := {j["right"][1]},\n'
            f'    m := {j["m"]}, n := {j["n"]},\n'
            f'    xdeg := {xdeg}, xsp := {xsp})')
    # PRED_C2GLUE_CHECK=0 disables the per-line self-checks (orbit-sum
    # identity + B<=P membership) for production-scale runs; default on.
    check = ("false" if os.environ.get("PRED_C2GLUE_CHECK") == "0"
             else "true")
    return (f"C2GLUE_CHECK := {check};\n"
            "JOBS := [\n" + ",\n".join(entries) + "\n];\n")


def run_gap(work, jobs, timeout):
    log = work / "c2glue.log"
    if log.exists():
        log.unlink()
    jobs_g = work / "jobs.g"
    jobs_g.write_text(gap_jobs_g(jobs), encoding="utf-8", newline="\n")
    run_g = work / "run.g"
    run_g.write_text(
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__LOG__", to_gap(log))
        .replace("__JOBS__", to_gap(jobs_g)),
        encoding="utf-8", newline="\n")

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = (r"C:\Program Files\GAP-4.15.1\runtime\bin;"
                   + env.get("PATH", ""))
    env["CYGWIN"] = "nodosfilewarning"
    sub_timeout = (None if (timeout is None or timeout <= 0
                            or timeout >= 86400 * 30) else timeout)
    subprocess.run(cmd, env=env, capture_output=True, text=True,
                   timeout=sub_timeout)
    return log.read_text(encoding="utf-8", errors="ignore") \
        if log.exists() else ""


RESULT_RE = re.compile(
    r"RESULT combo=(\S+) predicted=(\d+) candidates=(\d+) class_sum=(\d+)"
    r" n_src=(\d+) elapsed_ms=(\d+)")
NA_RE = re.compile(r"RESULT_NA combo=(\S+) reason=(\S+)")


def assemble_output(job, res):
    out = job["output_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# combo: {combo_header(job['combo'])}\n")
        f.write(f"# candidates: {res['candidates']}\n")
        f.write(f"# deduped: {res['predicted']}\n")
        f.write(f"# class_sum: {res['class_sum']}\n")
        f.write(f"# elapsed_ms: {res['elapsed_ms']}\n")
        f.write("# engine: c2_glue_stream\n")
        with job["body"].open("r", encoding="utf-8") as body:
            for line in body:
                f.write(line)
    tmp.replace(out)


def run_combos(combo_specs, source_dir, timeout=0, work_name=None):
    """combo_specs: list of (combo_str, output_path).  Runs all eligible
    jobs in ONE GAP session; returns a list of per-combo result dicts."""
    t0 = time.time()
    work = TMP_DIR / (work_name or
                      re.sub(r"[^\w,\[\]-]", "_", combo_specs[0][0])[:80])
    work.mkdir(parents=True, exist_ok=True)

    results, jobs = [], []
    for i, (combo_str, output_path) in enumerate(combo_specs):
        job = build_job(combo_str, output_path, source_dir, idx=i, work=work)
        if "error" in job:
            results.append({"combo": combo_str, **job})
        else:
            jobs.append(job)
    if not jobs:
        return results

    log_text = run_gap(work, jobs, timeout)
    elapsed = round(time.time() - t0, 1)

    by_combo = {m.group(1): m for m in RESULT_RE.finditer(log_text)}
    na_by_combo = {m.group(1): m.group(2) for m in NA_RE.finditer(log_text)}
    for job in jobs:
        key = job["combo_str"]
        if key in by_combo:
            m = by_combo[key]
            res = {
                "combo": key,
                "mode": "c2_glue_stream",
                "predicted": int(m.group(2)),
                "candidates": int(m.group(3)),
                "class_sum": int(m.group(4)),
                "n_source_lines": int(m.group(5)),
                "elapsed_ms": int(m.group(6)),
                # Per-job GAP time; the scheduler sums per-job elapsed_s, so
                # don't charge every job the whole session's wall time.
                "elapsed_s": round(int(m.group(6)) / 1000.0, 3),
                "session_elapsed_s": elapsed,
                "output_path": str(job["output_path"]),
            }
            assemble_output(job, res)
            results.append(res)
        elif key in na_by_combo:
            results.append({"combo": key, "mode": "c2_glue_stream",
                            "error": f"not applicable: {na_by_combo[key]}"})
        else:
            results.append({"combo": key, "mode": "c2_glue_stream",
                            "error": "no RESULT in GAP log",
                            "log_tail": log_text[-2000:]})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo")
    ap.add_argument("--output-path")
    ap.add_argument("--batch-json",
                    help="JSON list of {combo, output_path} run in one "
                         "GAP session")
    ap.add_argument("--source-dir",
                    default=os.environ.get("PREDICT_SN_DIR",
                                           str(ROOT / "parallel_sn_v3only")))
    ap.add_argument("--timeout", type=int, default=0)
    args = ap.parse_args()

    if args.batch_json:
        bj = Path(args.batch_json)
        specs = [(j["combo"], j["output_path"])
                 for j in json.loads(bj.read_text())]
        # Work dir keyed by the batch file's parent dir (the scheduler makes
        # one dir per chunk) — a bare "jobs.json" stem would collide across
        # concurrently-running chunks.
        results = run_combos(specs, args.source_dir, timeout=args.timeout,
                             work_name=f"{bj.parent.name}_{bj.stem}")
        print(json.dumps(results, indent=2))
    else:
        if not (args.combo and args.output_path):
            ap.error("--combo and --output-path required "
                     "(or use --batch-json)")
        results = run_combos([(args.combo, args.output_path)],
                             args.source_dir, timeout=args.timeout)
        print(json.dumps(results[0], indent=2))


if __name__ == "__main__":
    main()
