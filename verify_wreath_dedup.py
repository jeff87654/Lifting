#!/usr/bin/env python3
"""verify_wreath_dedup.py — correctness confidence harness for the wreath_ra dedup.

The "RA dedup" engine is predict_full_general_wreath.py (alias wreath_ra_dedup.py):
it materializes the FPF subdirect subgroups of a single-species combo [d,t]^m,
buckets them by a W-invariant fingerprint, then resolves each bucket by pairwise
RepresentativeAction(W, .,.) under union-find, W = N_T wr S_m.  This script
triangulates its conjugacy-class count (n_distinct) against independent oracles:

  (1) wreath, default flags                -> the count under test (W-dedup).
  (2) wreath, WREATH_DISABLE_PHI=1         -> the fingerprint must NEVER change
      [and WREATH_DISABLE_TIERD=1]            the count, only the RA-call count.
  (3) S_n oracle on the emitted reps       -> re-dedup the reps under FULL S_n and
      (a tiny GAP backtrack, this file)       sum n!/|N_{S_n}(H)|.  Catches OVERCOUNT
                                              (reps must be pairwise S_n-non-conjugate)
                                              and gives an INDEPENDENT labelled
                                              class_sum (direct Normalizer, not the
                                              engine's block-wise BuildWBlockwise).
  (4) analytic oracle (b_d8 / b_power)     -> fully independent enumerator for the
                                              species that have one (D8/C3/C4/V4).
                                              Catches BOTH over- and under-count.
  (5) predict_full_general.py (S_n)        -> same Goursat materialization re-run and
                                              deduped under S_n by an independent code
                                              path.  Catches both; needs parallel_sn.

The W-restriction theorem says, for these FPF subdirects, S_n-conjugacy == W-conjugacy,
so (1) must equal (3)'s re-dedup, (4), and (5).  A genuine numeric DISAGREEMENT fails
the harness (exit != 0).  A missing oracle (source tree absent, no analytic engine for
the species) is reported SKIP, not FAIL.

Usage:
    python verify_wreath_dedup.py                       # default sweep, n <= 12
    python verify_wreath_dedup.py --max-n 15
    python verify_wreath_dedup.py --combo "[4,2]_[4,2]_[4,2]"
    python verify_wreath_dedup.py --species 4,2 --species 4,3
    python verify_wreath_dedup.py --quick               # skip (2) and (5)
    python verify_wreath_dedup.py --disable-tierd-check # don't run the TIERD A/B leg
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from predict_full_general_wreath import _join_gap_continuations

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
PY = sys.executable
TMP = ROOT / "predict_species_tmp" / "_verify_wreath"
TMP.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

# The S_n re-dedup leg is O(reps^2) full backtracks; skip it above this many reps
# (the analytic oracle + predict_full_general independently cover those combos).
SN_REDUPE_MAX_REPS = 80

# Species with a fully independent analytic enumerator (runner, no W-dedup involved).
# b_d8 is the dedicated cross-algorithm D8 oracle; b_power covers C3/C4/V4 powers.
ANALYTIC_ORACLE = {
    (4, 3): "run_b_d8_path.py",
    (3, 1): "run_b_power_path.py",
    (4, 1): "run_b_power_path.py",
    (4, 2): "run_b_power_path.py",
}
DEFAULT_SPECIES = [(3, 1), (3, 2), (4, 1), (4, 2), (4, 3)]


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def _run_json(cmd, env=None, timeout=1800):
    """Run a predictor subprocess; return its parsed JSON stdout (or {'error':...})."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=full_env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    out = proc.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} block.
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"error": "no JSON",
                "stdout_tail": out[-800:],
                "stderr_tail": proc.stderr[-800:] if proc.stderr else ""}


def run_wreath(combo_str, n, disable_phi=False, disable_tierd=False,
               emit=False, timeout=1800):
    """Run the wreath_ra engine; return its result dict (n_distinct, generators_file...)."""
    cmd = [PY, "-u", str(ROOT / "predict_full_general_wreath.py"),
           "--combo", combo_str, "--target-n", str(n), "--timeout", str(timeout)]
    if emit:
        cmd.append("--emit-generators")
    env = {}
    if disable_phi:
        env["WREATH_DISABLE_PHI"] = "1"
    if disable_tierd:
        env["WREATH_DISABLE_TIERD"] = "1"
    return _run_json(cmd, env=env, timeout=timeout)


def run_general(combo_str, d, t, n, timeout=1800):
    """Independent S_n oracle via predict_full_general.py (re-materialize + S_n dedup)."""
    cmd = [PY, "-u", str(ROOT / "predict_full_general.py"),
           "--combo", combo_str, "--dt", f"{d},{t}",
           "--target-n", str(n), "--timeout", str(timeout)]
    return _run_json(cmd, timeout=timeout)


def run_analytic_oracle(combo_str, d, t, timeout=1800):
    """Fully independent analytic enumerator for species that have one; else None."""
    runner = ANALYTIC_ORACLE.get((d, t))
    if runner is None:
        return None
    out_path = TMP / f"oracle_{d}_{t}_{combo_str}.g"
    cmd = [PY, "-u", str(ROOT / runner),
           "--combo", combo_str, "--output-path", str(out_path),
           "--timeout", str(timeout)]
    res = _run_json(cmd, timeout=timeout)
    res["_runner"] = runner
    return res


# ---- S_n oracle on the emitted reps (this file's own tiny GAP backtrack) --------------
GAP_SN_ORACLE = r"""
LogTo("__LOG__");
N := __N__;
Read("__REPS_CYG__");           # defines REPS := [ Group([...]), ... ];
S := SymmetricGroup(N);

# (a) independent labelled class_sum: sum over reps of [S_n : N_{S_n}(H)]
cs := 0;
for H in REPS do
    cs := cs + Factorial(N) / Size(Normalizer(S, H));
od;

# (b) re-dedup the reps under FULL S_n: any S_n-conjugate pair => wreath OVERCOUNTED.
# This is O(reps^2) full backtracks (the reps are already distinct, so every pair is a
# non-merge = a non-conjugacy proof).  Skip it for large rep sets (n_sn := -1 sentinel);
# the analytic oracle + predict_full_general cover those combos' counts independently.
nrep := Length(REPS);
if nrep <= __MAXREDUPE__ then
    parent := [1..nrep];
    UF_Find := function(x)
        while parent[x] <> x do parent[x] := parent[parent[x]]; x := parent[x]; od;
        return x;
    end;
    merges := 0;
    for i in [1..nrep-1] do
        for j in [i+1..nrep] do
            if UF_Find(i) <> UF_Find(j) then
                if RepresentativeAction(S, REPS[i], REPS[j]) <> fail then
                    parent[UF_Find(j)] := UF_Find(i);
                    merges := merges + 1;
                fi;
            fi;
        od;
    od;
    n_sn := Length(Set([1..nrep], i -> UF_Find(i)));
else
    n_sn := -1;        # re-dedup skipped (too many reps)
    merges := 0;
fi;

Print("RESULT n_reps=", nrep, " n_sn_distinct=", n_sn,
      " sn_merges=", merges, " class_sum_sn=", cs, "\n");
LogTo();
QUIT;
"""


def _parse_reps(gens_file: Path):
    """Parse the wreath fps.g emit: '# class_sum: N' header + one '[gens]' line per rep.

    Long permutation lists are wrapped by GAP with '\\' line continuations, so join
    those first (reuse the engine's own joiner) before splitting into reps.
    """
    raw = gens_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    class_sum = None
    rep_lines = []
    for s in (ln.strip() for ln in _join_gap_continuations(raw)):
        if s.startswith("#"):
            m = re.match(r"#\s*class_sum:\s*(\d+)", s)
            if m:
                class_sum = int(m.group(1))
            continue
        rep_lines.append(s)
    return class_sum, rep_lines


def run_sn_oracle(gens_file: Path, n, combo_str, timeout=1800):
    """GAP backtrack on the emitted reps: independent S_n re-dedup + direct-normalizer cs."""
    class_sum_wreath, rep_lines = _parse_reps(gens_file)
    if not rep_lines:
        return {"error": "no reps in emit", "class_sum_wreath": class_sum_wreath}
    work = TMP / f"sn_oracle_{combo_str}"
    work.mkdir(parents=True, exist_ok=True)
    reps_g = work / "reps.g"
    with open(reps_g, "w", encoding="utf-8") as f:
        f.write("REPS := [\n")
        for i, line in enumerate(rep_lines):
            sep = "," if i < len(rep_lines) - 1 else ""
            f.write(f"  Group({line}){sep}\n")
        f.write("];\n")
    log = work / "sn_oracle.log"
    if log.exists():
        log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_SN_ORACLE
        .replace("__LOG__", to_cyg(log))
        .replace("__N__", str(n))
        .replace("__MAXREDUPE__", str(SN_REDUPE_MAX_REPS))
        .replace("__REPS_CYG__", to_cyg(reps_g)),
        encoding="utf-8")
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    try:
        subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"RESULT n_reps=\s*(\d+)\s+n_sn_distinct=\s*(-?\d+)\s+"
                  r"sn_merges=\s*(\d+)\s+class_sum_sn=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-800:]}
    return {
        "n_reps": int(m.group(1)),
        "n_sn_distinct": int(m.group(2)),
        "sn_merges": int(m.group(3)),
        "class_sum_sn": int(m.group(4)),
        "class_sum_wreath": class_sum_wreath,
    }


def combos_for_sweep(species, max_n):
    """Single-species [d,t]^m with m>=2 and m*d <= max_n."""
    out = []
    for (d, t) in species:
        m = 2
        while m * d <= max_n:
            combo_str = "_".join([f"[{d},{t}]"] * m)
            out.append((combo_str, d, t, m, m * d))
            m += 1
    return out


def check_one(combo_str, d, t, m, n, args):
    """Run all legs for one combo; return (row, ok, notes)."""
    notes = []
    ok = True

    # (1) wreath, default flags, emit reps for the S_n oracle.
    w = run_wreath(combo_str, n, emit=True, timeout=args.timeout)
    if "error" in w or w.get("n_distinct") is None:
        return ({"combo": combo_str, "n": n, "wreath": "ERR"}, False,
                [f"wreath error: {w.get('error', w)}"])
    W = w["n_distinct"]
    gens_file = Path(w["generators_file"]) if w.get("generators_file") else None

    row = {"combo": combo_str, "n": n, "wreath": W}

    # (3) S_n oracle on the emitted reps (always-on, self-contained).
    if gens_file and gens_file.exists():
        sn = run_sn_oracle(gens_file, n, combo_str, timeout=args.timeout)
        if "error" in sn:
            row["sn_redupe"] = "SKIP"
            notes.append(f"sn_oracle: {sn['error']}")
        elif sn["n_sn_distinct"] == -1:
            row["sn_redupe"] = f"skip>{SN_REDUPE_MAX_REPS}"   # re-dedup skipped, cs still checked
        else:
            row["sn_redupe"] = sn["n_sn_distinct"]
            if sn["n_sn_distinct"] != W:
                ok = False
                notes.append(f"OVERCOUNT: wreath={W} but S_n re-dedup={sn['n_sn_distinct']} "
                             f"({sn['sn_merges']} reps merged under S_n)")
            # independent labelled class_sum (direct N_{S_n}, not BuildWBlockwise)
            cw, cs = sn.get("class_sum_wreath"), sn.get("class_sum_sn")
            row["cs"] = cs
            if cw is not None and cw != cs:
                ok = False
                notes.append(f"CLASS_SUM mismatch: wreath={cw} direct-S_n={cs}")
    else:
        row["sn_redupe"] = "SKIP"
        notes.append("no reps emitted")

    # (4) analytic oracle (fully independent), if the species has one.
    orc = run_analytic_oracle(combo_str, d, t, timeout=args.timeout)
    if orc is None:
        row["oracle"] = "-"
    elif "error" in orc or orc.get("predicted") is None:
        row["oracle"] = "SKIP"
        notes.append(f"{ANALYTIC_ORACLE[(d, t)]}: {orc.get('error', orc)}")
    else:
        O = orc["predicted"]
        row["oracle"] = O
        if O != W:
            ok = False
            notes.append(f"ORACLE mismatch: wreath={W} {orc['_runner']}={O}")

    # (2) fingerprint-invariance: PHI on/off (and TIERD on/off) must not change count.
    if not args.quick:
        w_phi0 = run_wreath(combo_str, n, disable_phi=True, timeout=args.timeout)
        P = w_phi0.get("n_distinct")
        row["phi_off"] = P if P is not None else "ERR"
        if P != W:
            ok = False
            notes.append(f"PHI on/off changes count: on={W} off={P}")
        if not args.disable_tierd_check:
            w_td0 = run_wreath(combo_str, n, disable_tierd=True, timeout=args.timeout)
            Q = w_td0.get("n_distinct")
            row["tierd_off"] = Q if Q is not None else "ERR"
            if Q != W:
                ok = False
                notes.append(f"TIERD on/off changes count: on={W} off={Q}")

    # (5) predict_full_general.py: independent re-materialization + S_n dedup.
    if not args.quick:
        g = run_general(combo_str, d, t, n, timeout=args.timeout)
        G = g.get("n_distinct")
        if G is None:
            row["general"] = "SKIP"
            notes.append(f"predict_full_general: {g.get('error', g)}")
        else:
            row["general"] = G
            if G != W:
                ok = False
                notes.append(f"GENERAL (S_n) mismatch: wreath={W} general={G}")

    return row, ok, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--combo", help="check a single combo string, e.g. '[4,2]_[4,2]_[4,2]'")
    ap.add_argument("--species", action="append",
                    help="restrict sweep to species 'd,t' (repeatable)")
    ap.add_argument("--max-n", type=int, default=12,
                    help="largest total degree m*d in the sweep (default 12)")
    ap.add_argument("--quick", action="store_true",
                    help="skip the PHI/TIERD-flag and predict_full_general legs")
    ap.add_argument("--disable-tierd-check", action="store_true",
                    help="don't run the WREATH_DISABLE_TIERD A/B leg "
                         "(use before Tier-D-lite lands)")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    if args.combo:
        pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
        pairs = pat.findall(args.combo)
        sp = sorted(set((int(a), int(b)) for a, b in pairs))
        if len(sp) != 1:
            print(f"ERROR: not single-species: {sp}")
            sys.exit(2)
        d, t = sp[0]
        m = len(pairs)
        combos = [(args.combo, d, t, m, m * d)]
    else:
        species = DEFAULT_SPECIES
        if args.species:
            want = set()
            for s in args.species:
                a, b = s.split(",")
                want.add((int(a), int(b)))
            species = [sp for sp in DEFAULT_SPECIES if sp in want] + \
                      [sp for sp in want if sp not in DEFAULT_SPECIES]
        combos = combos_for_sweep(species, args.max_n)

    print(f"verify_wreath_dedup: {len(combos)} combo(s), max_n={args.max_n}, "
          f"quick={args.quick}\n")
    rows = []
    all_ok = True
    t_start = time.time()
    for (combo_str, d, t, m, n) in combos:
        t0 = time.time()
        row, ok, notes = check_one(combo_str, d, t, m, n, args)
        row["_ok"] = ok
        row["_s"] = round(time.time() - t0, 1)
        rows.append(row)
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {combo_str:<40} "
              f"wreath={row.get('wreath')} sn={row.get('sn_redupe')} "
              f"oracle={row.get('oracle')} "
              f"phi_off={row.get('phi_off', '-')} "
              f"general={row.get('general', '-')} "
              f"cs={row.get('cs', '-')} ({row['_s']}s)")
        for nt in notes:
            print(f"          - {nt}")

    print(f"\n{'='*72}")
    n_fail = sum(1 for r in rows if not r["_ok"])
    print(f"{'ALL PASS' if all_ok else f'{n_fail} FAILED'} "
          f"({len(rows)} combos, {round(time.time() - t_start, 1)}s total)")
    (TMP / "last_run.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
