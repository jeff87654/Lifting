#!/usr/bin/env python3
"""
predict_burnside_m2.py — Burnside orbit-counting for the m=2 case
(combos with exactly two same-species blocks).

For combo c that has one species (d, t) appearing twice, this script:
  1. Pivots on (d, t) to get source c' (one (d, t) less)
  2. Runs the predictor's BFS-based enumeration to get N×N-orbit reps of
     fiber products (K_H, K_T, phi) per source H
  3. For each orbit, computes the swap-image (K_T, K_H, phi^-1) and looks
     up its orbit id
  4. Burnside total: (n_NN + n_swap_fixed) / 2

For pure 2-block same-species [(d,t), (d,t)]: source c' = [(d,t)] is the
single-block base case.  The "source H" is just T itself.

For "extended" 2-block same-species like [(d,t), (d,t), (e,u)]: source c'
has [(d,t), (e,u)], distinguished species (e,u) -> we run the standard
predictor; only (d,t)-pivot triggers Burnside.

Output: predict_burnside_tmp/<combo>/from_<dt>/result.json with
  predicted (Burnside total), n_NN, n_swap_fixed, elapsed_s.
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
TMP = ROOT / "predict_species_tmp" / "_burnside_m2"
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


# Burnside m=2 GAP driver.
#
# Approach: for each H, enumerate all (K_H, K_T)-pair orbits with reps,
# then for each orbit compute swap-image and find its orbit id.
#
# Orbit identity: each iso phi: Q_T -> Q_H is hashed by its image on
# generators of Q_T (a list of group elements).  We store a key->orbit_idx
# dict per (K_H_idx, K_T_idx) pair.
#
# Swap action: phi at (K_H_a, K_T_b) maps to phi^-1 at (K_T_b, K_H_a)
# (where the source/target groups swap).  We look up phi^-1's orbit at
# the (K_T_b, K_H_a) bucket.  swap-fixed iff that orbit's "swap-image" is
# this orbit (consistency).
GAP_BURNSIDE = r"""
LogTo("__LOG__");

# inputs
M     := __M__;
DD    := __D__;
TID   := __T_ID__;
SUBS_PATH := "__SUBS_CYG__";

Print("burnside m=2: m=", M, " d=", DD, " t=", TID, "\n");

S_M := SymmetricGroup(M);
T   := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);
N_T := Normalizer(S_D, T);

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

# T-side data: list of records (K, hom, Q, qsize, qid, stab, AutQ, A_gens).
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
AllowedQids := Set(List(T_data, x -> x.qid));

Read(SUBS_PATH);   # SUBGROUPS

# For each H in SUBGROUPS, compute Burnside m=2 contribution.
# Returns rec(n_orbits := total NxN orbit count, n_swap_fixed := swap-fixed orbits).
ProcessH := function(H)
    local N_H, h_normals, K_H_data_list, k_orbit, k_data,
          a_idx, b_idx, KH_a, KT_b, A_H, A_T, isoTH,
          n_NN, n_swap_fixed, n_swap_fixed_local,
          phi_rep, swap_phi, swap_key,
          orbit_id, gens_QT, gens_QT_new, key_of, swap_iso_idx, swap_orbit_id,
          alpha, beta, q,
          orbits_data, orbit_count_table, isos, n_isos, idx, seen,
          orbit_reps, n_orb, queue, i, j, k, phi, neighbor, nkey,
          KH_K_to_idx, KT_K_to_idx, pkey, new_a_key, new_b_key,
          new_a_idx, new_b_idx, new_pkey, new_od, orec, orbit_idx_local;

    N_H := Normalizer(S_M, H);

    # If H == T as sets (pure 2-block same-species case), reuse T_data
    # entries so Q objects share families with T-side and the swap-fix check
    # works.  Otherwise build fresh K_H_data_list from H.
    if H = T then
        K_H_data_list := T_data;
    else
        K_H_data_list := [];
        for k_orbit in Orbits(N_H, NormalSubgroups(H), ConjAction) do
            k_data := rec(K := k_orbit[1]);
            k_data.hom := NaturalHomomorphismByNormalSubgroup(H, k_data.K);
            k_data.Q := Range(k_data.hom);
            k_data.qsize := Size(k_data.Q);
            k_data.qid := SafeId(k_data.Q);
            k_data.stab := Stabilizer(N_H, k_data.K, ConjAction);
            if k_data.qsize > 1 then
                k_data.AutQ := AutomorphismGroup(k_data.Q);
                k_data.A_gens := InducedAutoGens(k_data.stab, H, k_data.hom);
            else
                k_data.AutQ := fail;
                k_data.A_gens := [];
            fi;
            Add(K_H_data_list, k_data);
        od;
    fi;

    # For each (a, b) pair, enumerate (Stab_a x Stab_b)-orbits on Iso(Q_T_b, Q_H_a)
    # via BFS.  Store: per pair, a list of orbit reps (as iso objects) and a
    # key->orbit_idx dict (key = list of images of gens(Q_T_b)).
    # Iso enumeration: phi = a_T * isoTH where a_T runs over Aut(Q_T_b) and
    # isoTH = IsomorphismGroups(Q_T_b, Q_H_a).
    orbits_data := rec();   # keyed by Concatenation("a", a_idx, "b", b_idx)
    orbit_count_table := rec();   # same key -> n_orbits

    n_NN := 1;   # trivial-quotient direct product H x T
    n_swap_fixed := 1;

    # Build all per-(a,b) orbit data first
    for a_idx in [1..Length(K_H_data_list)] do
        if K_H_data_list[a_idx].qsize <= 1 then continue; fi;
        for b_idx in [1..Length(T_data)] do
            if T_data[b_idx].qsize <= 1 then continue; fi;
            if K_H_data_list[a_idx].qid <> T_data[b_idx].qid then continue; fi;

            isoTH := IsomorphismGroups(T_data[b_idx].Q, K_H_data_list[a_idx].Q);
            if isoTH = fail then continue; fi;

            # Enumerate isos: Aut(Q_T_b) elements composed with isoTH.
            isos := List(AsList(T_data[b_idx].AutQ), aT -> aT * isoTH);
            n_isos := Length(isos);
            gens_QT := GeneratorsOfGroup(T_data[b_idx].Q);
            key_of := function(phi)
                return List(gens_QT, q -> Image(phi, q));
            end;

            # idx: stringified key -> position in isos
            idx := rec();
            for i in [1..n_isos] do
                idx.(String(key_of(isos[i]))) := i;
            od;

            # BFS per orbit
            seen := ListWithIdenticalEntries(n_isos, false);
            orbit_id := ListWithIdenticalEntries(n_isos, 0);
            n_orb := 0;
            orbit_reps := [];
            A_H := K_H_data_list[a_idx].A_gens;
            A_T := T_data[b_idx].A_gens;

            for i in [1..n_isos] do
                if seen[i] then continue; fi;
                n_orb := n_orb + 1;
                Add(orbit_reps, isos[i]);
                queue := [i];
                seen[i] := true;
                orbit_id[i] := n_orb;
                while Length(queue) > 0 do
                    j := Remove(queue);
                    phi := isos[j];
                    for alpha in A_H do
                        neighbor := phi * alpha;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then
                                seen[k] := true; orbit_id[k] := n_orb; Add(queue, k);
                            fi;
                        fi;
                    od;
                    for beta in A_T do
                        neighbor := InverseGeneralMapping(beta) * phi;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then
                                seen[k] := true; orbit_id[k] := n_orb; Add(queue, k);
                            fi;
                        fi;
                    od;
                od;
            od;

            pkey := Concatenation("a", String(a_idx), "b", String(b_idx));
            orbits_data.(pkey) := rec(
                isos := isos, idx := idx, orbit_id := orbit_id,
                orbit_reps := orbit_reps, n_orb := n_orb,
                isoTH := isoTH, AutQ_a := K_H_data_list[a_idx].AutQ,
                AutQ_b := T_data[b_idx].AutQ,
                Q_a := K_H_data_list[a_idx].Q, Q_b := T_data[b_idx].Q,
                a_idx := a_idx, b_idx := b_idx
            );
            orbit_count_table.(pkey) := n_orb;

            n_NN := n_NN + n_orb;
        od;
    od;

    # Now for each orbit at (a, b), compute swap-image and check if in same orbit
    # at (b', a') where (b', a') has K_H = K_T_b's K and K_T = K_H_a's K.
    # NOTE: For Burnside m=2 with H = T (pure 2-block same-species), K_H_data_list
    # corresponds 1-1 with T_data (when matching K's).
    # Otherwise (extended 2-block-repeat), the swap goes outside the predictor's
    # source frame and this method is not directly applicable.

    # Build map from K_T's K to its index in K_H_data_list (and vice versa).
    # If H = T, both lists have the same K's (by construction since both are
    # NormalSubgroups orbits under the same group action, when H == T).
    KH_K_to_idx := rec();
    for i in [1..Length(K_H_data_list)] do
        KH_K_to_idx.(String(GeneratorsOfGroup(K_H_data_list[i].K))) := i;
    od;
    KT_K_to_idx := rec();
    for i in [1..Length(T_data)] do
        KT_K_to_idx.(String(GeneratorsOfGroup(T_data[i].K))) := i;
    od;

    n_swap_fixed_local := 0;
    # Self-pair only: K_H == K_T as subgroups.  For cross-pairs, orbits pair
    # 1-1 across (a,b) and (b,a) under swap and contribute 0 swap-fixed.
    for pkey in RecNames(orbits_data) do
        orec := orbits_data.(pkey);
        KH_a := K_H_data_list[orec.a_idx].K;
        KT_b := T_data[orec.b_idx].K;
        if KH_a <> KT_b then continue; fi;

        for orbit_idx_local in [1..orec.n_orb] do
            phi_rep := orec.orbit_reps[orbit_idx_local];
            swap_phi := InverseGeneralMapping(phi_rep);
            # phi: Q_b -> Q_a. swap_phi: Q_a -> Q_b. Self-pair: Q_a = Q_b
            # (when K_H == K_T as subgroups), so swap_phi is in same iso space.
            gens_QT_new := GeneratorsOfGroup(orec.Q_b);
            swap_key := String(List(gens_QT_new, q -> Image(swap_phi, q)));
            if not IsBound(orec.idx.(swap_key)) then continue; fi;
            swap_iso_idx := orec.idx.(swap_key);
            swap_orbit_id := orec.orbit_id[swap_iso_idx];
            if swap_orbit_id = orbit_idx_local then
                n_swap_fixed_local := n_swap_fixed_local + 1;
            fi;
        od;
    od;

    n_swap_fixed := n_swap_fixed + n_swap_fixed_local;
    return rec(n_orbits := n_NN, n_swap_fixed := n_swap_fixed);
end;

TOTAL_NN := 0;
TOTAL_FIXED := 0;
for i in [1..Length(SUBGROUPS)] do
    res := ProcessH(SUBGROUPS[i]);
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


def write_subgroups_g(out_path: Path, subs: list[str]):
    with open(out_path, "w") as f:
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")


def predict_burnside_m2(target_combo: tuple, dt: tuple[int, int],
                        target_n: int = 18, timeout: int = 1800) -> dict:
    """Run Burnside m=2 prediction for a combo with species dt appearing twice."""
    # Source = target minus one (d, t) block
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
    write_subgroups_g(subs_g, subs)
    log = work / "burnside.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_BURNSIDE
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
        return {"error": "no RESULT", "log_tail": log_text[-1000:], "elapsed_s": elapsed}
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
    ap.add_argument("--combo", required=True,
                    help='target combo string e.g. "[5,5]_[5,5]_[8,1]" (note: not all are NON_PREDICTABLE)')
    ap.add_argument("--dt", required=True, help='species to pivot on, e.g. "5,5"')
    ap.add_argument("--target-n", type=int, default=18, help="Target S_n (default 18)")
    args = ap.parse_args()

    # Parse combo and dt
    pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
    combo_pairs = pat.findall(args.combo)
    target_combo = tuple(sorted((int(d), int(t)) for d, t in combo_pairs))
    d_str, t_str = args.dt.split(",")
    dt = (int(d_str.strip()), int(t_str.strip()))

    print(f"Target: {target_combo}")
    print(f"Pivot:  {dt}")
    print(f"target_n: {args.target_n}")
    if Counter(target_combo)[dt] != 2:
        print(f"WARNING: dt appears {Counter(target_combo)[dt]} times, not 2 (m != 2)")

    result = predict_burnside_m2(target_combo, dt, target_n=args.target_n)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
