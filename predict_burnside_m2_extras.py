#!/usr/bin/env python3
"""
predict_burnside_m2_extras.py — Burnside m=2 for combos where the source has
EXTRA distinguished species besides the repeated one.

For combo c with one species (d, t) appearing twice + other species each
once, source c' = [(d,t), X_1, ..., X_k] is fully distinguished.

The Burnside formula is the same:
    distinct = (n_NN + n_swap_fixed) / 2

The challenge is computing n_swap_fixed when H != T (source has extras).
The swap exchanges the (d,t) block in source-H with the new T block.  This
changes H's "(d,t)-part" but keeps X_i unchanged.  We can't compare Goursat
data directly across H's (d,t)-part vs T because they live in different
families.

Instead: for each orbit rep, MATERIALIZE one fiber product G (just one per
orbit, NOT all candidates).  Apply the swap permutation to get G^swap.
Check if G^swap is N(H)×N(T)-conjugate to G via RA.

This is cheap per orbit (one materialization + one RA in N×N) and avoids
materializing all candidates.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
SN_DIR = ROOT / "parallel_sn"
S18_DIR = ROOT / "parallel_s18"
TMP = ROOT / "predict_species_tmp" / "_burnside_m2_extras"
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


GAP_BURNSIDE_EXTRAS = r"""
LogTo("__LOG__");

# Load _GoursatBuildFiberProduct from lifting_algorithm.g
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

M     := __M__;
DD    := __D__;
TID   := __T_ID__;
TARGET_N := M + DD;
SUBS_PATH := "__SUBS_CYG__";

Print("burnside m=2+extras: m=", M, " d=", DD, " t=", TID,
      " target_n=", TARGET_N, "\n");

S_M := SymmetricGroup(M);
T_orig := TransitiveGroup(DD, TID);
# Shift T to act on [M+1..M+D]
shift := MappingPermListList([1..DD], [M+1..M+DD]);
T := T_orig^shift;
N_T := Normalizer(SymmetricGroup([M+1..M+DD]), T);
S_TARGET := SymmetricGroup(TARGET_N);

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

# For each H in SUBGROUPS, compute Burnside m=2 contribution.
# Identify H's (d,t) block by orbit length and transitive identification.
ProcessH := function(H)
    local N_H, h_normals, K_H_data, k_orbit, kh_data,
          a_idx, b_idx, isoTH,
          isos, n_isos, gens_QT, key_of, idx, seen, queue,
          orbit_id, orbit_reps, n_orb, i, j, phi, neighbor, nkey, k,
          alpha, beta, q,
          n_NN_local, n_swap_fixed_local,
          orbit_idx, rep_phi, fp, swap_perm, fp_swapped, NxN, H_orbit_pts,
          H_orbits_list, ot, action_grp, t_id, AutQ, gens_isos, phi_inv;

    N_H := Normalizer(S_M, H);
    h_normals := NormalSubgroups(H);

    # Find H's (d, t) orbit block: the orbit on [1..M] where H acts as TG(d, t).
    H_orbit_pts := fail;
    for ot in OrbitsDomain(H, [1..M]) do
        if Length(ot) = DD then
            action_grp := Action(H, ot);
            if Size(action_grp) = Size(T_orig) then
                t_id := TransitiveIdentification(action_grp);
                if t_id = TID then
                    H_orbit_pts := ot;
                    break;
                fi;
            fi;
        fi;
    od;
    if H_orbit_pts = fail then
        Print("WARNING: H has no (", DD, ",", TID, ") orbit\n");
        return rec(n_orbits := 1, n_swap_fixed := 1);
    fi;

    # Swap permutation: exchanges H_orbit_pts with [M+1..M+DD]
    H_orbit_pts := AsList(H_orbit_pts);  # ensure list form, length DD
    swap_perm := MappingPermListList(
        Concatenation(H_orbit_pts, [M+1..M+DD]),
        Concatenation([M+1..M+DD], H_orbit_pts));

    # NxN: subgroup of S_TARGET = direct product of N_H (acting on [1..M])
    # and N_T (acting on [M+1..M+DD]).
    NxN := Group(Concatenation(GeneratorsOfGroup(N_H), GeneratorsOfGroup(N_T)));

    K_H_data := [];
    for k_orbit in Orbits(N_H, h_normals, ConjAction) do
        kh_data := rec(K := k_orbit[1]);
        kh_data.hom := NaturalHomomorphismByNormalSubgroup(H, kh_data.K);
        kh_data.Q := Range(kh_data.hom);
        kh_data.qsize := Size(kh_data.Q);
        kh_data.qid := SafeId(kh_data.Q);
        kh_data.stab := Stabilizer(N_H, kh_data.K, ConjAction);
        if kh_data.qsize > 1 then
            kh_data.AutQ := AutomorphismGroup(kh_data.Q);
            kh_data.A_gens := InducedAutoGens(kh_data.stab, H, kh_data.hom);
        else
            kh_data.AutQ := fail;
            kh_data.A_gens := [];
        fi;
        Add(K_H_data, kh_data);
    od;

    # Trivial-quotient direct product: just H × T as subgroup of S_TARGET
    # using their existing point sets ([1..M] for H, [M+1..M+DD] for T).
    fp := Group(Concatenation(GeneratorsOfGroup(H), GeneratorsOfGroup(T)));
    fp_swapped := fp^swap_perm;
    n_NN_local := 1;
    if RepresentativeAction(NxN, fp, fp_swapped) <> fail then
        n_swap_fixed_local := 1;
    else
        n_swap_fixed_local := 0;
    fi;

    for a_idx in [1..Length(K_H_data)] do
        if K_H_data[a_idx].qsize <= 1 then continue; fi;
        if not (K_H_data[a_idx].qsize in AllowedSizes) then continue; fi;
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
            orbit_reps := [];
            n_orb := 0;
            for i in [1..n_isos] do
                if seen[i] then continue; fi;
                n_orb := n_orb + 1;
                Add(orbit_reps, isos[i]);
                queue := [i];
                seen[i] := true;
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
            od;

            n_NN_local := n_NN_local + n_orb;

            # Materialize one fiber product per orbit, apply swap, RA-check
            for orbit_idx in [1..n_orb] do
                rep_phi := orbit_reps[orbit_idx];
                # _GoursatBuildFiberProduct expects phi: Q1 -> Q2 where T1=H, T2=T
                # Our isos are Q_T -> Q_H. Invert to get Q_H -> Q_T.
                phi_inv := InverseGeneralMapping(rep_phi);
                fp := _GoursatBuildFiberProduct(
                    H, T,
                    K_H_data[a_idx].hom, T_data[b_idx].hom,
                    phi_inv,
                    [1..M], [M+1..M+DD]);
                if fp = fail then continue; fi;

                fp_swapped := fp^swap_perm;
                if RepresentativeAction(NxN, fp, fp_swapped) <> fail then
                    n_swap_fixed_local := n_swap_fixed_local + 1;
                fi;
            od;
        od;
    od;

    return rec(n_orbits := n_NN_local, n_swap_fixed := n_swap_fixed_local);
end;

TOTAL_NN := 0;
TOTAL_FIXED := 0;
for H_idx in [1..Length(SUBGROUPS)] do
    res := ProcessH(SUBGROUPS[H_idx]);
    TOTAL_NN := TOTAL_NN + res.n_orbits;
    TOTAL_FIXED := TOTAL_FIXED + res.n_swap_fixed;
od;

burnside := (TOTAL_NN + TOTAL_FIXED) / 2;
Print("RESULT n_NN=", TOTAL_NN,
      " swap_fixed=", TOTAL_FIXED,
      " burnside=", burnside, "\n");
LogTo();
QUIT;
"""


def predict_burnside_extras(target_combo, dt, target_n=18, timeout=1800):
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

    log = work / "burnside.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_BURNSIDE_EXTRAS
        .replace("__LOG__", to_cyg(log))
        .replace("__M__", str(src_n))
        .replace("__D__", str(dt[0]))
        .replace("__T_ID__", str(dt[1]))
        .replace("__SUBS_CYG__", to_cyg(subs_g))
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
    m = re.search(r"RESULT n_NN=\s*(\d+)\s+swap_fixed=\s*(\d+)\s+burnside=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:], "elapsed_s": elapsed}
    return {
        "n_NN": int(m.group(1)),
        "n_swap_fixed": int(m.group(2)),
        "predicted": int(m.group(3)),
        "elapsed_s": elapsed,
        "src_n": src_n,
        "src_file": str(src_file),
        "subgroup_count": len(subs),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--dt", required=True, help='repeated species, e.g. "5,5"')
    ap.add_argument("--target-n", type=int, default=18)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
    combo_pairs = pat.findall(args.combo)
    target_combo = tuple(sorted((int(d), int(t)) for d, t in combo_pairs))
    d_str, t_str = args.dt.split(",")
    dt = (int(d_str.strip()), int(t_str.strip()))

    print(f"Target: {target_combo}, pivot: {dt}, target_n: {args.target_n}")
    if Counter(target_combo)[dt] != 2:
        print(f"WARNING: dt appears {Counter(target_combo)[dt]} times, not 2")

    result = predict_burnside_extras(target_combo, dt,
                                      target_n=args.target_n, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
