#!/usr/bin/env python3
"""labelled_postpass.py

Scalable parallel post-pass: compute per-rep class sizes (cs = m!/|N_W(H)|) for
every persisted FPF representative, using the validated block-wise W builder in
labelled_oracle.g.  Writes a per-combo sidecar (# class_sum / # class_sizes) in
the gitignored parallel_sn_topt/_labelled_cs/ tree, then aggregates L_FPF(m),
binomial-transforms to L(n), and checks against OEIS A005432.

Workers process disjoint chunks of combo files (embarrassingly parallel), each in
its own GAP session that reads the combo files directly (no rep embedding).

Usage:
  python labelled_postpass.py --m-min 2 --m-max 18 --workers 8
  python labelled_postpass.py --aggregate-only --m-max 18
"""
from __future__ import annotations
import argparse
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"C:/Users/jeffr/Downloads/Lifting")
# Honor PREDICT_SN_DIR for fresh-run dirs (e.g. parallel_sn_topt_labelled).
# Resolve to absolute so GAP, which runs from its own cwd, finds the files.
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn_topt"))).resolve()
# CS_DIR / WORK_DIR are env-overridable so a --force-recompute *verify* run can
# write to a separate tree WITHOUT clobbering the build's sidecars.  Must be at
# MODULE level (not a main() global reassignment): ProcessPoolExecutor spawns
# workers that RE-IMPORT this module, so a main()-time override wouldn't reach
# them (that bug wrote chunk manifests to the default _labelled_work and every
# chunk failed with "No such file").
CS_DIR = Path(os.environ.get("LABELLED_CS_DIR") or str(SN_DIR / "_labelled_cs")).resolve()
WORK_DIR = Path(os.environ.get("LABELLED_WORK_DIR") or str(SN_DIR / "_labelled_work")).resolve()

A005432 = [
    1, 1, 2, 6, 30, 156, 1455, 11300, 151221, 1694723, 29594446, 404126228,
    10594925360, 175238308453, 5651774693595, 117053117995400,
    5320744503742316, 125889331236297288, 7598016157515302757,
]

BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAPDIR = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def parse_partition(name):
    return tuple(int(x) for x in name.strip("[]").split(",") if x.strip())


def sidecar_path(m, part, combo):
    return CS_DIR / str(m) / part / (combo + ".cs")


def collect_combo_files(m_min, m_max):
    items = []
    for m in range(m_min, m_max + 1):
        mdir = SN_DIR / str(m)
        if not mdir.is_dir():
            continue
        for part_dir in sorted(p for p in mdir.iterdir() if p.is_dir()):
            for f in sorted(part_dir.glob("*.g")):
                items.append((m, part_dir.name, f.stem, f))
    return items


def sidecar_valid(sc):
    if not sc.exists():
        return False
    try:
        txt = sc.read_text(encoding="utf-8")
    except OSError:
        return False
    return "# class_sum:" in txt and "# class_sizes:" in txt


def parse_combo(combo_stem):
    """[2,1]_[3,2]_[4,3]  ->  list of (d, t) tuples."""
    return [(int(a), int(b))
            for a, b in re.findall(r"\[(\d+),(\d+)\]", combo_stem)]


# Pure-power harvest engines.  Each entry: (d, t) -> (gap_load, gap_call(k))
# where gap_call(k) is a GAP expression returning a class_sum integer.
PURE_POWER_HARVEST = {
    (4, 3): ('Read("C:/Users/jeffr/Downloads/Lifting/b_d8_harvest.g");',
             "BD8_ClassSumUC({k}).class_sum"),
    (4, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_c4_harvest.g");',
             "BC4_ClassSumUC({k}).class_sum"),
    (3, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(3, 1, {k}).class_sum"),
    (4, 2): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(2, 2, {k}).class_sum"),
    (2, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(2, 1, {k}).class_sum"),
    # F_p^k for primes p with TransitiveGroup(p,1) elementary abelian:
    (5, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(5, 1, {k}).class_sum"),
    (7, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(7, 1, {k}).class_sum"),
    (8, 3): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(2, 3, {k}).class_sum"),  # E_8 = C2^3
    (9, 2): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
             "BElemab_ClassSumWithSizes(3, 2, {k}).class_sum"),  # E_9 = C3^2
    (11, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
              "BElemab_ClassSumWithSizes(11, 1, {k}).class_sum"),
    (13, 1): ('Read("C:/Users/jeffr/Downloads/Lifting/b_elemab_harvest.g");',
              "BElemab_ClassSumWithSizes(13, 1, {k}).class_sum"),
}


def is_pure_power(combo):
    """Return (d, t, k) if combo is a pure power (d,t)^k with k >= 2 and
    a registered harvest engine, else None."""
    if len(combo) < 2:
        return None
    d, t = combo[0]
    if all(x == (d, t) for x in combo):
        if (d, t) in PURE_POWER_HARVEST:
            return (d, t, len(combo))
    return None


def _gap_run(manifest, env):
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    gapdir = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
    script_cyg = "/cygdrive/c" + manifest.as_posix()[2:]
    proc = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "{gapdir}" && ./gap.exe -q -o 0 "{script_cyg}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        cwd=r"C:\Program Files\GAP-4.15.1\runtime")
    out, err = proc.communicate()
    return out, err


def run_chunk_pure_power(chunk_id, jobs):
    """Pure-power jobs: invoke harvest engines.  jobs are tuples
    (m, part, combo, sc_str, d, t, k).  Writes one sidecar per job with
    # class_sum (per-rep class_sizes omitted; harvest yields the sum directly)."""
    manifest = WORK_DIR / f"chunk_pp_{chunk_id}.g"
    # collect distinct (d,t) so we only Read each engine file once
    loads = sorted({PURE_POWER_HARVEST[(d, t)][0]
                    for (_m, _p, _c, _sc, d, t, _k) in jobs})
    lines = list(loads)
    for (m, part, combo, sc_str, d, t, k) in jobs:
        call = PURE_POWER_HARVEST[(d, t)][1].format(k=k)
        lines.append(f'_cs := {call};')
        lines.append(
            f'_f := OutputTextFile("{sc_str}", false);')
        lines.append('AppendTo(_f, "# class_sum: ", _cs, "\\n");')
        lines.append(f'AppendTo(_f, "# source: pure_power_harvest_(d={d},t={t},k={k})\\n");')
        lines.append('AppendTo(_f, "# class_sizes: (omitted; class_sum is exact via harvest)\\n");')
        lines.append('CloseStream(_f);')
    lines.append("QUIT;")
    manifest.write_text("\n".join(lines), encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    out, err = _gap_run(manifest, env)
    return chunk_id, "pure_power", err[-500:] if err else ""


def run_chunk(chunk_id, jobs):
    """Fallback (Normalizer-in-W per rep) for non-pure-power combos.
    jobs = list of (m, part, combo, path_str, sidecar_str)."""
    manifest = WORK_DIR / f"chunk_{chunk_id}.g"
    resfile = WORK_DIR / f"chunk_{chunk_id}.res"
    lines = ['Read("C:/Users/jeffr/Downloads/Lifting/labelled_oracle.g");']
    lines.append(f'_R := OutputTextFile("{resfile.as_posix()}", false);')
    for (m, part, combo, path_str, sc_str) in jobs:
        lines.append(
            f'_x := ProcessComboFileToSidecar("{path_str}", {m}, "{sc_str}");')
        lines.append(
            f'if _x = fail then AppendTo(_R, "FAIL {chunk_id} {m}\\n"); else '
            f'AppendTo(_R, "OK ", _x[1], " ", _x[2], " {m} '
            f'{part}|{combo}\\n"); fi;')
    lines.append("CloseStream(_R);")
    lines.append("QUIT;")
    manifest.write_text("\n".join(lines), encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    script_cyg = "/cygdrive/c" + manifest.as_posix()[2:]
    proc = subprocess.Popen(
        [BASH, "--login", "-c",
         f'cd "{GAPDIR}" && ./gap.exe -q -o 0 "{script_cyg}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        cwd=r"C:\Program Files\GAP-4.15.1\runtime")
    out, err = proc.communicate()
    return chunk_id, resfile, err[-500:] if err else ""


def aggregate(m_min, m_max):
    """Read all sidecars, sum per m and per partition, binomial-transform."""
    L_FPF = {0: 1, 1: 0}
    by_part = {}
    missing = []
    for (m, part, combo, f) in collect_combo_files(m_min, m_max):
        sc = sidecar_path(m, part, combo)
        if not sidecar_valid(sc):
            missing.append((m, part, combo))
            continue
        txt = sc.read_text(encoding="utf-8")
        cs = int(re.search(r"# class_sum:\s*(\d+)", txt).group(1))
        L_FPF[m] = L_FPF.get(m, 0) + cs
        by_part[(m, part)] = by_part.get((m, part), 0) + cs
    return L_FPF, by_part, missing


def report(L_FPF, by_part, m_max):
    f = [L_FPF.get(m, 0) for m in range(m_max + 1)]
    L = [sum(math.comb(n, m) * f[m] for m in range(n + 1)) for n in range(m_max + 1)]
    print("\n=== L(n) vs A005432 ===")
    ok = True
    for n in range(m_max + 1):
        oeis = A005432[n] if n < len(A005432) else None
        if oeis is None:
            flag = "NEW-TERM"
        else:
            flag = "OK" if L[n] == oeis else f"MISMATCH(expected {oeis})"
            ok = ok and (L[n] == oeis)
        print(f"  L({n:2d}) = {L[n]:<22d} {flag}")
    summary = {
        "L_FPF": {m: f[m] for m in range(m_max + 1)},
        "L": {n: L[n] for n in range(m_max + 1)},
        "by_partition": {f"{m}:{p}": v for (m, p), v in sorted(by_part.items())},
    }
    (SN_DIR / "_labelled_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote {SN_DIR / '_labelled_summary.json'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m-min", type=int, default=2)
    ap.add_argument("--m-max", type=int, default=18)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk-size", type=int, default=40,
                    help="combo files per GAP session")
    ap.add_argument("--aggregate-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="recompute sidecars even if present")
    ap.add_argument("--force-recompute", action="store_true",
                    help="INDEPENDENT verify: skip the inline class_sum fast path; "
                         "recompute EVERY combo via Normalizer-in-W / harvest, so the "
                         "result is independent of the engine's cached class_sum.  Point "
                         "it at a separate tree with env LABELLED_CS_DIR / LABELLED_WORK_DIR "
                         "so it doesn't clobber the build's sidecars.")
    args = ap.parse_args()

    # NOTE: --force-recompute controls ONLY the inline-skip routing (recompute
    # independently of the engine cache).  It does NOT imply --force, so a
    # verify run RESUMES: existing valid (independent) sidecars are kept and
    # only missing ones are computed.  Pass --force explicitly to redo all.
    CS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    if not args.aggregate_only:
        items = collect_combo_files(args.m_min, args.m_max)
        pp_todo = []      # pure-power harvest
        fb_todo = []      # post-pass fallback (Normalizer in W)
        inline_count = 0  # combo file already carries `# class_sum:` from a
                          # harvest-instrumented run; copy it to the sidecar.
        for (m, part, combo, f) in items:
            sc = sidecar_path(m, part, combo)
            if not (args.force or not sidecar_valid(sc)):
                continue
            sc.parent.mkdir(parents=True, exist_ok=True)
            # Fast path: if the combo file already has # class_sum (engine
            # harvest), reuse it directly.
            try:
                head = f.read_text(encoding="utf-8", errors="ignore")[:2048]
            except OSError:
                head = ""
            m_cs = re.search(r"^# class_sum:\s*(\d+)", head, re.MULTILINE)
            if m_cs and not args.force_recompute:
                sc.write_text(
                    f"# class_sum: {m_cs.group(1)}\n"
                    f"# source: inline_from_engine_harvest\n"
                    f"# class_sizes: (in combo file)\n",
                    encoding="utf-8")
                inline_count += 1
                continue
            pp = is_pure_power(parse_combo(combo))
            if pp is not None:
                d, t, k = pp
                pp_todo.append((m, part, combo, sc.as_posix(), d, t, k))
            else:
                fb_todo.append((m, part, combo, f.as_posix(), sc.as_posix()))
        print(f"  inline (engine harvest already in combo file): {inline_count}")
        print(f"{len(items)} combo files;  "
              f"pure-power harvest: {len(pp_todo)};  "
              f"post-pass fallback: {len(fb_todo)}")
        pp_chunks = [pp_todo[i:i + args.chunk_size]
                     for i in range(0, len(pp_todo), args.chunk_size)]
        fb_chunks = [fb_todo[i:i + args.chunk_size]
                     for i in range(0, len(fb_todo), args.chunk_size)]
        print(f"{len(pp_chunks)} pp + {len(fb_chunks)} fb chunks "
              f"across {args.workers} workers.")
        done = 0
        total = len(pp_chunks) + len(fb_chunks)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for i, c in enumerate(pp_chunks):
                futs[ex.submit(run_chunk_pure_power, i, c)] = ("pp", i)
            for i, c in enumerate(fb_chunks):
                futs[ex.submit(run_chunk, i, c)] = ("fb", i)
            for fut in as_completed(futs):
                kind, cid = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"  chunk {kind} {cid} EXC: {e}")
                done += 1
                if done % 20 == 0 or done == total:
                    print(f"  {done}/{total} chunks done")

    L_FPF, by_part, missing = aggregate(args.m_min, args.m_max)
    if missing:
        print(f"!! {len(missing)} combos missing sidecars, e.g. {missing[:5]}")
    ok = report(L_FPF, by_part, args.m_max)
    print(f"RESULT ok={ok}")
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
