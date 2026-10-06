#!/usr/bin/env python3
"""
run_c2_glue2_path.py — streaming C2^2-glue engine driver (peel_c2_pair family).

For combos with EXACTLY TWO (2,1) blocks plus a non-degree-2 cluster X, the
RIGHT cluster's structure is fixed and tiny (two FPF classes: C2^2 and the
diagonal C2; glue quotients {1, C2, V4}; Aut collapse under the block-swap
D8 hand-derived), so every class is entry-local per LEFT line: X's already
built output .g is streamed line by line through c2_glue2_path_writer.g —
no LEFT H-cache, O(1) memory.  Replaces the general peel_c2_pair pair loop
(the n=20 `[2,1]^2_[4,3]^4` monster: 3.88M classes at ~5 ms/class there).

Usage (single combo):
    python run_c2_glue2_path.py --combo "[2,1]_[2,1]_[4,3]" \
        --output-path out.g --source-dir parallel_sn_topt_fresh_0604

Batch (one GAP session for many combos; used by the validation sweep):
    python run_c2_glue2_path.py --batch-json jobs.json --source-dir ...
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
TEMPLATE = ROOT / "c2_glue2_path_writer.g"
TMP_DIR = Path(os.environ.get(
    "PREDICT_TMP_DIR", str(ROOT / "predict_species_tmp" / "_c2_glue2")))

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


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


def source_deduped_header(src):
    """The source's `# deduped:` header (its own class count), or None when
    absent.  Used to cross-check the streamed line count: a truncated source
    (non-atomic writer killed mid-write, stale file in a recovery tree) would
    otherwise pass through silently as a complete-looking undercount."""
    try:
        with src.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    break
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        pass
    return None


def build_job(combo_str, output_path, source_dir, idx=0, work=None):
    combo = parse_combo(combo_str)
    if combo.count((2, 1)) != 2:
        return {"error": "needs exactly two (2,1) blocks"}
    x_combo = list(combo)
    x_combo.remove((2, 1))
    x_combo.remove((2, 1))
    x_combo = tuple(x_combo)
    if not x_combo:
        return {"error": "pure [2,1]^2 is c2_fast territory"}
    if any(d == 2 for d, _ in x_combo):
        return {"error": "more than two degree-2 blocks"}
    m = sum(d for d, _ in x_combo)
    n = m + 4
    src = (Path(source_dir).resolve() / str(m)
           / partition_dir([d for d, _ in x_combo])
           / (combo_to_str(x_combo) + ".g"))
    if not src.exists():
        return {"error": f"left source not found: {src}"}
    src_deduped = source_deduped_header(src)
    if src_deduped is None:
        return {"error": f"left source has no # deduped: header: {src}"}
    return {
        "combo": combo,
        "combo_str": combo_to_str(combo),
        "x_combo": x_combo,
        "m": m,
        "n": n,
        "src": src,
        "src_deduped": src_deduped,
        "output_path": Path(output_path),
        "body": (work / f"body_{idx}.g") if work else None,
    }


def gap_jobs_g(jobs) -> str:
    entries = []
    for j in jobs:
        xsp = "[" + ",".join(f"[{d},{t}]" for d, t in j["x_combo"]) + "]"
        xdeg = "[" + ",".join(str(d) for d, _ in j["x_combo"]) + "]"
        lo, hi = j.get("line_lo", 0), j.get("line_hi", 0)
        entries.append(
            f'rec(combo := "{j["combo_str"]}",\n'
            f'    src := "{to_gap(j["src"])}",\n'
            f'    body := "{to_gap(j["body"])}",\n'
            f'    m := {j["m"]}, n := {j["n"]},\n'
            f'    line_lo := {lo}, line_hi := {hi},\n'
            f'    xdeg := {xdeg}, xsp := {xsp})')
    check = ("false" if os.environ.get("PRED_C2GLUE_CHECK") == "0"
             else "true")
    return (f"C2GLUE_CHECK := {check};\n"
            "JOBS := [\n" + ",\n".join(entries) + "\n];\n")


def run_gap(work, jobs, timeout):
    log = work / "c2glue2.log"
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
        f.write("# engine: c2_glue2_stream\n")
        with job["body"].open("r", encoding="utf-8") as body:
            for line in body:
                f.write(line)
    tmp.replace(out)


def run_combos(combo_specs, source_dir, timeout=0, work_name=None):
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
                "mode": "c2_glue2_stream",
                "predicted": int(m.group(2)),
                "candidates": int(m.group(3)),
                "class_sum": int(m.group(4)),
                "n_source_lines": int(m.group(5)),
                "elapsed_ms": int(m.group(6)),
                "elapsed_s": round(int(m.group(6)) / 1000.0, 3),
                "session_elapsed_s": elapsed,
                "output_path": str(job["output_path"]),
            }
            # Source-integrity cross-check: the streamed line count must
            # equal the source's own # deduped: header.  A truncated source
            # would otherwise become a complete-looking undercount here.
            if res["n_source_lines"] != job["src_deduped"]:
                results.append({
                    "combo": key, "mode": "c2_glue2_stream",
                    "error": (f"streamed {res['n_source_lines']} source lines"
                              f" but source header says # deduped: "
                              f"{job['src_deduped']} (truncated/corrupt "
                              f"source: {job['src']})")})
                continue
            assemble_output(job, res)
            results.append(res)
        elif key in na_by_combo:
            results.append({"combo": key, "mode": "c2_glue2_stream",
                            "error": f"not applicable: {na_by_combo[key]}"})
        else:
            results.append({"combo": key, "mode": "c2_glue2_stream",
                            "error": "no RESULT in GAP log",
                            "log_tail": log_text[-2000:]})
    return results


def count_source_lines(src) -> int:
    """Generator-list lines in a combo .g (one '['-prefixed line per class;
    multi-line lists count once via bracket balance)."""
    n = depth = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if depth == 0:
                if not line or line[0] != "[":
                    continue
                n += 1
            depth += line.count("[") - line.count("]")
    return n


def run_sharded(combo_str, output_path, source_dir, n_shards, timeout=0):
    """Fan a single combo out over n_shards parallel GAP sessions by source
    line range, then merge (sum headers, concat bodies).  Per-line work is
    independent, so the merged deduped/class_sum are exact."""
    import concurrent.futures as cf
    job = build_job(combo_str, output_path, source_dir)
    if "error" in job:
        return job
    total = count_source_lines(job["src"])
    if total != job["src_deduped"]:
        return {"combo": combo_str,
                "error": (f"source has {total} generator lines but its "
                          f"header says # deduped: {job['src_deduped']} "
                          f"(truncated/corrupt source: {job['src']})")}
    n_shards = max(1, min(n_shards, total))
    bounds = [(k * total // n_shards + 1, (k + 1) * total // n_shards)
              for k in range(n_shards)]
    work = TMP_DIR / (re.sub(r"[^\w,\[\]-]", "_", combo_str)[:60] + "_shards")
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    results = []
    with cf.ThreadPoolExecutor(max_workers=n_shards) as pool:
        futs = []
        for k, (lo, hi) in enumerate(bounds):
            swork = TMP_DIR / f"{work.name}_{k}"
            swork.mkdir(parents=True, exist_ok=True)
            sjob = dict(job)
            sjob["body"] = swork / "body_0.g"
            sjob["line_lo"], sjob["line_hi"] = lo, hi
            sjob["output_path"] = work / f"shard_{k}.g"
            futs.append(pool.submit(_run_one_shard, swork, sjob, timeout))
        for f in futs:
            results.append(f.result())

    bad = [r for r in results if "error" in r]
    if bad:
        return {"combo": combo_str, "error": f"shard failures: {bad[:3]}"}
    merged = {
        "combo": combo_str,
        "mode": f"c2_glue2_stream_x{n_shards}",
        "predicted": sum(r["predicted"] for r in results),
        "candidates": sum(r["candidates"] for r in results),
        "class_sum": sum(r["class_sum"] for r in results),
        "n_source_lines": sum(r["n_source_lines"] for r in results),
        "elapsed_ms": max(r["elapsed_ms"] for r in results),
        "elapsed_s": round(time.time() - t0, 3),
        "output_path": str(output_path),
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# combo: {combo_header(job['combo'])}\n")
        f.write(f"# candidates: {merged['candidates']}\n")
        f.write(f"# deduped: {merged['predicted']}\n")
        f.write(f"# class_sum: {merged['class_sum']}\n")
        f.write(f"# elapsed_ms: {merged['elapsed_ms']}\n")
        f.write(f"# engine: c2_glue2_stream shards={n_shards}\n")
        for k in range(n_shards):
            with (work / f"shard_{k}.g").open("r", encoding="utf-8") as bf:
                for line in bf:
                    if not line.startswith("#"):
                        f.write(line)
    tmp.replace(out)
    return merged


def _run_one_shard(swork, sjob, timeout):
    log_text = run_gap(swork, [sjob], timeout)
    m = RESULT_RE.search(log_text)
    if not m:
        na = NA_RE.search(log_text)
        return {"combo": sjob["combo_str"],
                "error": (f"NA: {na.group(2)}" if na
                          else f"no RESULT; tail: {log_text[-500:]}")}
    res = {
        "combo": sjob["combo_str"],
        "predicted": int(m.group(2)),
        "candidates": int(m.group(3)),
        "class_sum": int(m.group(4)),
        "n_source_lines": int(m.group(5)),
        "elapsed_ms": int(m.group(6)),
    }
    # shard body -> shard output file (headerless body is fine for merge)
    sjob["output_path"].parent.mkdir(parents=True, exist_ok=True)
    Path(sjob["body"]).replace(sjob["output_path"])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo")
    ap.add_argument("--output-path")
    ap.add_argument("--batch-json")
    ap.add_argument("--shards", type=int, default=1,
                    help="fan a single combo over N parallel GAP sessions "
                         "by source line range; counts merge exactly")
    ap.add_argument("--source-dir",
                    default=os.environ.get("PREDICT_SN_DIR",
                                           str(ROOT / "parallel_sn_opt0610")))
    ap.add_argument("--timeout", type=int, default=0)
    args = ap.parse_args()

    if args.combo and args.shards > 1:
        if not args.output_path:
            ap.error("--output-path required")
        result = run_sharded(args.combo, args.output_path, args.source_dir,
                             args.shards, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return

    if args.batch_json:
        bj = Path(args.batch_json)
        specs = [(j["combo"], j["output_path"])
                 for j in json.loads(bj.read_text())]
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
