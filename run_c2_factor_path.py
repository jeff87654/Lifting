#!/usr/bin/env python3
"""
Fast path for two-factor combos C2 x T.

For a combo [2,1]_[d,t], Goursat's lemma leaves only two left quotients:
the trivial quotient and C2. Thus the FPF subdirects are:
  - the direct product C2 x T;
  - one fiber product for each index-2 normal subgroup K of T, deduped in S_n.

This avoids the generic quotient catalogue / H-cache path, which is far too
expensive when the right factor has many transitive groups (e.g. [12,2]).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TMP_DIR = Path(os.environ.get(
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_c2_factor")))
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


def gap_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def c2_factor_job(combo_str, output_path):
    combo = parse_combo(combo_str)
    if len(combo) != 2 or (2, 1) not in combo:
        raise ValueError(f"not a C2-factor two-combo: {combo_str}")
    other = [pair for pair in combo if pair != (2, 1)]
    if len(other) != 1:
        raise ValueError(f"ambiguous C2-factor combo: {combo_str}")
    d, tnum = other[0]
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_str = "_".join(f"[{a},{b}]" for a, b in combo)
    return {
        "combo": target_str,
        "d": d,
        "tnum": tnum,
        "output_path": output_path,
    }


GAP_TEMPLATE = r'''
LogTo("__LOG_PATH__");

D := __D__;
TNUM := __TNUM__;
OUTPUT_PATH := "__OUTPUT_PATH__";
COMBO_HEADER := "# combo: [ [ 2, 1 ], [ __D__, __TNUM__ ] ]";

job_t0 := Runtime();
N := D + 2;
S := SymmetricGroup(N);
C2 := Group((1,2));
T := TransitiveGroup(D, TNUM);
shift_R := MappingPermListList([1..D], [3..D+2]);
T_shifted := T^shift_R;

Candidates := [];
Add(Candidates, Group(Concatenation(
    GeneratorsOfGroup(C2), GeneratorsOfGroup(T_shifted))));

normals := NormalSubgroups(T);
for K in normals do
    if Size(K) < Size(T) and Size(T) / Size(K) = 2 then
        rep := First(GeneratorsOfGroup(T), g -> not g in K);
        if rep = fail then
            Error("index-2 normal subgroup had no generator outside it");
        fi;
        K_shifted := K^shift_R;
        Add(Candidates, Group(Concatenation(
            GeneratorsOfGroup(K_shifted), [(1,2) * (rep^shift_R)])));
    fi;
od;

Reps := [];
for G in Candidates do
    if not ForAny(Reps, H -> RepresentativeAction(S, H, G) <> fail) then
        Add(Reps, G);
    fi;
od;

elapsed_ms := Runtime() - job_t0;
TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
OUT_STREAM := OutputTextFile(TMP_OUT, false);
SetPrintFormattingStatus(OUT_STREAM, false);
WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(Length(Candidates)), "\n"));
WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(Length(Reps)), "\n"));
WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
for G in Reps do
    WriteAll(OUT_STREAM, Concatenation(String(GeneratorsOfGroup(G)), "\n"));
od;
CloseStream(OUT_STREAM);
Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

Print("RESULT predicted=", Length(Reps),
      " candidates=", Length(Candidates),
      " index2=", Length(Candidates) - 1,
      " elapsed_ms=", elapsed_ms, "\n");

LogTo();
QUIT;
'''


GAP_BATCH_TEMPLATE = r'''
LogTo("__LOG_PATH__");

JOBS := [
__JOBS_BODY__
];

RunC2FactorJob := function(JOB, job_idx)
    local D, TNUM, OUTPUT_PATH, COMBO_HEADER, job_t0, N, S, C2, T,
          shift_R, T_shifted, Candidates, normals, K, rep, K_shifted,
          Reps, G, elapsed_ms, TMP_OUT, OUT_STREAM;

    D := JOB.d;
    TNUM := JOB.tnum;
    OUTPUT_PATH := JOB.output_path;
    COMBO_HEADER := Concatenation("# combo: [ [ 2, 1 ], [ ",
                                  String(D), ", ", String(TNUM), " ] ]");

    job_t0 := Runtime();
    N := D + 2;
    S := SymmetricGroup(N);
    C2 := Group((1,2));
    T := TransitiveGroup(D, TNUM);
    shift_R := MappingPermListList([1..D], [3..D+2]);
    T_shifted := T^shift_R;

    Candidates := [];
    Add(Candidates, Group(Concatenation(
        GeneratorsOfGroup(C2), GeneratorsOfGroup(T_shifted))));

    normals := NormalSubgroups(T);
    for K in normals do
        if Size(K) < Size(T) and Size(T) / Size(K) = 2 then
            rep := First(GeneratorsOfGroup(T), g -> not g in K);
            if rep = fail then
                Error("index-2 normal subgroup had no generator outside it");
            fi;
            K_shifted := K^shift_R;
            Add(Candidates, Group(Concatenation(
                GeneratorsOfGroup(K_shifted), [(1,2) * (rep^shift_R)])));
        fi;
    od;

    Reps := [];
    for G in Candidates do
        if not ForAny(Reps, H -> RepresentativeAction(S, H, G) <> fail) then
            Add(Reps, G);
        fi;
    od;

    elapsed_ms := Runtime() - job_t0;
    TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
    OUT_STREAM := OutputTextFile(TMP_OUT, false);
    SetPrintFormattingStatus(OUT_STREAM, false);
    WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
    WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(Length(Candidates)), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(Length(Reps)), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
    for G in Reps do
        WriteAll(OUT_STREAM, Concatenation(String(GeneratorsOfGroup(G)), "\n"));
    od;
    CloseStream(OUT_STREAM);
    Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

    Print("RESULT idx=", job_idx,
          " combo=", JOB.combo,
          " predicted=", Length(Reps),
          " candidates=", Length(Candidates),
          " index2=", Length(Candidates) - 1,
          " elapsed_ms=", elapsed_ms, "\n");
end;

for job_idx in [1..Length(JOBS)] do
    RunC2FactorJob(JOBS[job_idx], job_idx);
od;

LogTo();
QUIT;
'''


def run_c2_factor(combo_str, output_path, timeout=3600):
    t0 = time.time()
    try:
        job = c2_factor_job(combo_str, output_path)
    except ValueError as e:
        return {"error": str(e)}
    d = job["d"]
    tnum = job["tnum"]
    output_path = job["output_path"]

    target_str = job["combo"]
    work = TMP_DIR / target_str
    work.mkdir(parents=True, exist_ok=True)
    log = work / "c2_factor.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_TEMPLATE
        .replace("__LOG_PATH__", to_cyg(log))
        .replace("__OUTPUT_PATH__", to_cyg(output_path))
        .replace("__D__", str(d))
        .replace("__TNUM__", str(tnum)),
        encoding="utf-8",
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    sub_timeout = None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30) else timeout
    try:
        if sub_timeout is None:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                                  timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}

    elapsed = round(time.time() - t0, 1)
    if proc.returncode != 0:
        return {"error": f"GAP rc={proc.returncode}",
                "stderr": proc.stderr[-1000:],
                "stdout": proc.stdout[-1000:],
                "elapsed_s": elapsed}

    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(
        r"RESULT predicted=\s*(\d+)\s+candidates=\s*(\d+)\s+index2=\s*(\d+)\s+elapsed_ms=\s*(\d+)",
        log_text,
    )
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    return {
        "combo": target_str,
        "mode": "c2_factor",
        "predicted": int(m.group(1)),
        "candidates": int(m.group(2)),
        "index2": int(m.group(3)),
        "elapsed_s": elapsed,
        "output_path": str(output_path),
    }


def run_c2_factor_batch(batch_path, timeout=3600):
    t0 = time.time()
    try:
        raw_jobs = json.loads(Path(batch_path).read_text(encoding="utf-8-sig"))
        jobs = [c2_factor_job(j["combo"], j["output_path"]) for j in raw_jobs]
    except Exception as e:
        return [{"error": f"batch setup failed: {e}"}]

    batch_id = hashlib.sha1(
        json.dumps([(j["combo"], str(j["output_path"])) for j in jobs],
                   sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    work = TMP_DIR / f"batch_{batch_id}"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "c2_factor_batch.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"

    job_lines = []
    for j in jobs:
        job_lines.append(
            "rec(combo := {combo}, d := {d}, tnum := {tnum}, output_path := {out})".format(
                combo=gap_quote(j["combo"]),
                d=j["d"],
                tnum=j["tnum"],
                out=gap_quote(to_cyg(j["output_path"])),
            )
        )
    run_g.write_text(
        GAP_BATCH_TEMPLATE
        .replace("__LOG_PATH__", to_cyg(log))
        .replace("__JOBS_BODY__", ",\n".join(job_lines)),
        encoding="utf-8",
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    sub_timeout = None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30) else timeout
    try:
        if sub_timeout is None:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                                  timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return [{"combo": j["combo"], "mode": "c2_factor",
                 "output_path": str(j["output_path"]), "error": "timeout",
                 "elapsed_s": time.time() - t0} for j in jobs]

    elapsed = round(time.time() - t0, 1)
    if proc.returncode != 0:
        return [{"combo": j["combo"], "mode": "c2_factor",
                 "output_path": str(j["output_path"]),
                 "error": f"GAP rc={proc.returncode}",
                 "stderr": proc.stderr[-1000:],
                 "stdout": proc.stdout[-1000:],
                 "elapsed_s": elapsed} for j in jobs]

    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    rx = re.compile(
        r"RESULT idx=\s*(\d+)\s+combo=(\S+)\s+predicted=\s*(\d+)\s+"
        r"candidates=\s*(\d+)\s+index2=\s*(\d+)\s+elapsed_ms=\s*(\d+)"
    )
    by_idx = {}
    for m in rx.finditer(log_text):
        by_idx[int(m.group(1))] = {
            "combo": m.group(2),
            "mode": "c2_factor",
            "predicted": int(m.group(3)),
            "candidates": int(m.group(4)),
            "index2": int(m.group(5)),
            "elapsed_s": round(int(m.group(6)) / 1000.0, 3),
        }

    results = []
    for i, j in enumerate(jobs, start=1):
        if i in by_idx:
            results.append({**by_idx[i], "output_path": str(j["output_path"])})
        else:
            results.append({
                "combo": j["combo"],
                "mode": "c2_factor",
                "output_path": str(j["output_path"]),
                "error": "missing RESULT",
                "log_tail": log_text[-2000:],
                "elapsed_s": elapsed,
            })
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo")
    ap.add_argument("--output-path")
    ap.add_argument("--batch")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    if args.batch:
        result = run_c2_factor_batch(args.batch, timeout=args.timeout)
    else:
        if not args.combo or not args.output_path:
            ap.error("--combo and --output-path are required without --batch")
        result = run_c2_factor(args.combo, args.output_path, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
