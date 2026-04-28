#!/usr/bin/env python3
"""
predict_full_general.py — fully general predictor for any combo, including
NON_PREDICTABLE (multi-repeat species).

Approach: pick any species (d, t) appearing in the combo (need not be
distinguished).  For each H in source:
  1. Enumerate (Stab_NH × Stab_NT)-orbit reps of (K_H, K_T, φ) triples.
  2. For each orbit rep, MATERIALIZE the fiber product G ≤ S_n via
     _GoursatBuildFiberProduct from lifting_algorithm.g.
  3. Collect all materialized fiber products.

Then run pairwise RA-dedup in S_n on the materialized fiber products.
This handles arbitrary symmetry structure (any cycle type in any wreath).

Usage:
    python predict_full_general.py --combo "[5,5]_[5,5]_[8,1]" --dt "5,5" --target-n 18

Output: predict_full_tmp/<combo>/from_<dt>/result.json with predicted, n_NN
(materialized count), n_distinct (after RA dedup), elapsed_s.
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

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
SN_DIR = ROOT / "parallel_sn"
S18_DIR = ROOT / "parallel_s18"
TMP = ROOT / "predict_species_tmp" / "_full_general"
TMP.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace(): i += 1; continue
        if text[i] != "[": i += 1; continue
        depth = 0; j = i
        while j < n:
            ch = text[j]
            if ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0: break
            j += 1
        if j >= n: break
        out.append(text[i:j+1])
        i = j + 1
    return out


# Materialize + RA-dedup driver.
#
# Reuses existing _GoursatBuildFiberProduct from lifting_algorithm.g.
# Per H in SUBGROUPS:
#   For each (K_H_orbit, K_T_orbit, iso) triple in the (Stab × Stab)-action:
#     Build fiber product G via Goursat
#     Add to global ALL_FP list
# After all H processed: RA-dedup ALL_FP in S_n via union-find with
# IdGroup-fingerprint bucketing.
GAP_FULL = r"""
LogTo("__LOG__");

# Load Goursat helper from lifting_algorithm.g
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# inputs
M     := __M__;
DD    := __D__;
TID   := __T_ID__;
TARGET_N := M + DD;
SUBS_PATH := "__SUBS_CYG__";

Print("full general: m=", M, " d=", DD, " t=", TID, " target_n=", TARGET_N, "\n");

S_M := SymmetricGroup(M);
T_orig := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);

# T should act on points [M+1 .. M+D] (disjoint from H-side [1..M])
shift := MappingPermListList([1..DD], [M+1..M+DD]);
T := T_orig^shift;

S_TARGET := SymmetricGroup(TARGET_N);
N_T := Normalizer(SymmetricGroup([M+1..M+DD]), T);

ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

# T-side data
T_data := List(Orbits(N_T, NormalSubgroups(T), ConjAction),
               orbit -> rec(K := orbit[1]));
for r in T_data do
    r.hom := NaturalHomomorphismByNormalSubgroup(T, r.K);
    r.Q := Range(r.hom);
    r.qsize := Size(r.Q);
    r.qid := SafeId(r.Q);
    r.stab := Stabilizer(N_T, r.K, ConjAction);
    if r.qsize > 1 then
        r.AutQ := AutomorphismGroup(r.Q);
        r.A_gens := InducedAutoGens(r.stab, T, r.hom);
    else
        r.AutQ := fail;
        r.A_gens := [];
    fi;
od;
AllowedSizes := Set(List(T_data, x -> x.qsize));

Read(SUBS_PATH);   # SUBGROUPS

# Per-H materialization: iterate (K_H_orbit, K_T_orbit) pairs, BFS for orbit
# reps, then build fiber product per orbit rep via _GoursatBuildFiberProduct.
ALL_FP := [];

ProcessH := function(H)
    local N_H, h_normals, eligible, K_H_orbit_list, K_H_data,
          a_idx, b_idx, kh_data, t_data_b, isoTH,
          isos, n_isos, gens_QT, key_of, idx, seen, queue,
          orbit_id, orbit_reps, n_orb, i, j, phi, neighbor, nkey, k,
          alpha, beta, q, fp, hom_H_to_QT, phi_inv;

    N_H := Normalizer(S_M, H);
    h_normals := NormalSubgroups(H);

    # Trivial-quotient direct product
    fp := DirectProduct(H, T);
    Add(ALL_FP, fp);

    # Per K_H orbit (allowed quotient sizes only)
    eligible := Filtered(h_normals, K -> K <> H and (Index(H, K) in AllowedSizes));
    K_H_data := [];
    for orec in Orbits(N_H, eligible, ConjAction) do
        kh_data := rec(K := orec[1]);
        kh_data.hom := NaturalHomomorphismByNormalSubgroup(H, kh_data.K);
        kh_data.Q := Range(kh_data.hom);
        kh_data.qsize := Size(kh_data.Q);
        kh_data.qid := SafeId(kh_data.Q);
        kh_data.stab := Stabilizer(N_H, kh_data.K, ConjAction);
        if kh_data.qsize > 1 then
            kh_data.A_gens := InducedAutoGens(kh_data.stab, H, kh_data.hom);
        else
            kh_data.A_gens := [];
        fi;
        Add(K_H_data, kh_data);
    od;

    for a_idx in [1..Length(K_H_data)] do
        if K_H_data[a_idx].qsize <= 1 then continue; fi;
        for b_idx in [1..Length(T_data)] do
            if T_data[b_idx].qsize <= 1 then continue; fi;
            if K_H_data[a_idx].qid <> T_data[b_idx].qid then continue; fi;

            isoTH := IsomorphismGroups(T_data[b_idx].Q, K_H_data[a_idx].Q);
            if isoTH = fail then continue; fi;

            isos := List(AsList(T_data[b_idx].AutQ), aT -> aT * isoTH);
            n_isos := Length(isos);
            gens_QT := GeneratorsOfGroup(T_data[b_idx].Q);
            key_of := function(phi)
                return List(gens_QT, q -> Image(phi, q));
            end;
            idx := rec();
            for i in [1..n_isos] do
                idx.(String(key_of(isos[i]))) := i;
            od;

            seen := ListWithIdenticalEntries(n_isos, false);
            for i in [1..n_isos] do
                if seen[i] then continue; fi;
                queue := [i];
                seen[i] := true;
                # Mark the whole orbit as seen
                while Length(queue) > 0 do
                    j := Remove(queue);
                    phi := isos[j];
                    for alpha in K_H_data[a_idx].A_gens do
                        neighbor := phi * alpha;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then seen[k] := true; Add(queue, k); fi;
                        fi;
                    od;
                    for beta in T_data[b_idx].A_gens do
                        neighbor := InverseGeneralMapping(beta) * phi;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then seen[k] := true; Add(queue, k); fi;
                        fi;
                    od;
                od;
                # Build fiber product for the orbit-rep iso isos[i]
                # _GoursatBuildFiberProduct(T1, T2, hom1, hom2, phi, pts1, pts2)
                # We need phi: Q1 → Q2 where T1=H (Q1 = K_H_data[a_idx].Q),
                # T2 = T (Q2 = T_data[b_idx].Q).  Our isos[i] is Q_T_b → Q_H_a;
                # we want Q_H_a → Q_T_b, so invert.
                phi_inv := InverseGeneralMapping(isos[i]);
                fp := _GoursatBuildFiberProduct(
                    H, T,
                    K_H_data[a_idx].hom, T_data[b_idx].hom,
                    phi_inv,
                    [1..M], [M+1..M+DD]);
                if fp <> fail then
                    Add(ALL_FP, fp);
                fi;
            od;
        od;
    od;
end;

# Run materialization
t0 := Runtime();
for H_idx in [1..Length(SUBGROUPS)] do
    ProcessH(SUBGROUPS[H_idx]);
od;
mat_elapsed := Runtime() - t0;
n_materialized := Length(ALL_FP);
Print("materialized: ", n_materialized, " fiber products in ", mat_elapsed, "ms\n");

# RA-dedup with fingerprint bucketing
t1 := Runtime();
fp_fingerprint := function(G)
    local sz, abi;
    sz := Size(G);
    abi := AbelianInvariants(G);
    if IdGroupsAvailable(sz) then
        return [sz, IdGroup(G), abi];
    fi;
    return [sz, abi, List(DerivedSeries(G), Size)];
end;

fps := List(ALL_FP, fp_fingerprint);
parent := [1..n_materialized];
UF_Find := function(x)
    while parent[x] <> x do
        parent[x] := parent[parent[x]]; x := parent[x];
    od;
    return x;
end;
UF_Union := function(x, y)
    local rx, ry;
    rx := UF_Find(x); ry := UF_Find(y);
    if rx <> ry then parent[ry] := rx; fi;
end;

bucket := rec();
for i in [1..n_materialized] do
    bkey := String(fps[i]);
    if not IsBound(bucket.(bkey)) then bucket.(bkey) := []; fi;
    Add(bucket.(bkey), i);
od;

n_conj_pairs := 0;
for bkey in RecNames(bucket) do
    bk := bucket.(bkey);
    for i in [1..Length(bk)-1] do
        for j in [i+1..Length(bk)] do
            if UF_Find(bk[i]) = UF_Find(bk[j]) then continue; fi;
            if RepresentativeAction(S_TARGET, ALL_FP[bk[i]], ALL_FP[bk[j]]) <> fail then
                UF_Union(bk[i], bk[j]);
                n_conj_pairs := n_conj_pairs + 1;
            fi;
        od;
    od;
od;
classes := Set([1..n_materialized], i -> UF_Find(i));
n_distinct := Length(classes);
ra_elapsed := Runtime() - t1;
Print("RA dedup: ", n_distinct, " distinct from ", n_materialized,
      " (", n_conj_pairs, " conj pairs, ", ra_elapsed, "ms)\n");

Print("RESULT n_materialized=", n_materialized,
      " n_distinct=", n_distinct,
      " predicted=", n_distinct, "\n");
LogTo();
QUIT;
"""


def predict_full_general(target_combo, dt, target_n=18, timeout=1800):
    c_prime_list = list(target_combo)
    c_prime_list.remove(dt)
    c_prime = tuple(sorted(c_prime_list))
    src_n = target_n - dt[0]

    src_partition = "[" + ",".join(str(d) for d, _ in sorted(c_prime, reverse=True)) + "]"
    src_combo_name = "_".join(f"[{d},{t}]" for d, t in sorted(c_prime))
    src_file = SN_DIR / str(src_n) / src_partition / f"{src_combo_name}.g"
    if not src_file.exists():
        return {"error": f"src not found: {src_file}"}

    target_str = "_".join(f"[{d},{t}]" for d, t in sorted(target_combo))
    work = TMP / target_str / f"from_{dt[0]}_{dt[1]}"
    work.mkdir(parents=True, exist_ok=True)

    subs = parse_combo_file(src_file)
    if not subs:
        return {"error": "empty source"}
    subs_g = work / "subs.g"
    with open(subs_g, "w") as f:
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")
    log = work / "full.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_FULL
        .replace("__LOG__", to_cyg(log))
        .replace("__M__", str(src_n))
        .replace("__D__", str(dt[0]))
        .replace("__T_ID__", str(dt[1]))
        .replace("__SUBS_CYG__", to_cyg(subs_g)),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    elapsed = round(time.time() - t0, 1)

    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"RESULT n_materialized=\s*(\d+)\s+n_distinct=\s*(\d+)\s+predicted=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:], "elapsed_s": elapsed}
    return {
        "n_materialized": int(m.group(1)),
        "n_distinct": int(m.group(2)),
        "predicted": int(m.group(3)),
        "elapsed_s": elapsed,
        "src_n": src_n,
        "src_file": str(src_file),
        "subgroup_count": len(subs),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--dt", required=True)
    ap.add_argument("--target-n", type=int, default=18)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
    combo_pairs = pat.findall(args.combo)
    target_combo = tuple(sorted((int(d), int(t)) for d, t in combo_pairs))
    d_str, t_str = args.dt.split(",")
    dt = (int(d_str.strip()), int(t_str.strip()))

    print(f"Target: {target_combo}, pivot: {dt}, target_n: {args.target_n}")
    result = predict_full_general(target_combo, dt, target_n=args.target_n, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
