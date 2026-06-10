#!/usr/bin/env python3
"""
predict_full_general_wreath.py — single-cluster [d,t]^m predictor.

================================================================================
THIS IS THE "wreath_ra" ENGINE / THE "RA dedup" / "canonical-form dedup" worker.
(alias module: wreath_ra_dedup.py — searches for those names land here.)

What the dedup does, in one line:
    materialize FPF subdirect subgroups  ->  bucket by a W-invariant fingerprint
    ->  pairwise RepresentativeAction(W, .,.) backstop under union-find.

Grep map (all inside the GAP_WREATH string below):
    fp_fingerprint / fp_fingerprint_rich  - the W-invariant bucket keys
    PHI_* (PHI_Vec/PHI_Summary/PHI_ENABLED) - Tier-A mod-2 abelianization gluing
                                              code (WEN_SAFE-gated weight enum)
    canonPhi / TIERDLITE_ENABLED          - Tier-D-lite canonical-form abelian key
                                              (always-safe; see tier_d_canonical_form.md)
    UF_Find / UF_Union                    - union-find over the RA merges
    RepresentativeAction(W, ...)          - the exact pairwise backstop, W = N_T wr S_m
    WREATH_DISABLE_PHI / WREATH_DISABLE_TIERD - A/B env flags for the two keys
Also a TESTING WORKHORSE: --candidates-from dedups candidate sets from other engines.
Correctness oracle: predict_full_general.py (same dedup under full S_n).
================================================================================

Same approach as predict_full_general.py (materialize per Aut(Q)-orbit,
then pairwise RA-dedup with fingerprint bucketing) but uses the smaller
ambient group N_T wr S_m instead of full S_(m*d).  For the FPF subdirect
products we materialize, every S_n-conjugacy must be by an element of
N_T wr S_m (since both subgroups have the same m-block FPF structure of
species (d,t), and the conjugating element must preserve that structure).

This makes RA pairwise tests much cheaper -- |N_T wr S_m| << |S_n| for
larger m -- without any change to correctness vs. predict_full_general.py.

Usage:
    python predict_full_general_wreath.py --combo "[3,1]_[3,1]_[3,1]_[3,1]_[3,1]_[3,1]" --target-n 18
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
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn")))
TMP = Path(os.environ.get("PREDICT_TMP_DIR",
                          str(ROOT / "predict_species_tmp" / "_full_general_wreath")))
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


GAP_WREATH = r"""
LogTo("__LOG__");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# inputs
M     := __M__;       # source degree (= (m_blocks - 1) * d)
DD    := __D__;
TID   := __T_ID__;
M_BLOCKS := __M_BLOCKS__;   # total # of (d,t) blocks (m_blocks)
TARGET_N := M + DD;
SUBS_PATH := "__SUBS_CYG__";
# When MATERIALIZE = 0, skip the local Goursat (T_data + ProcessH) and load
# pre-materialized candidate groups from CANDIDATES_PATH instead.  Each line
# in that file should be a bracketed permutation generator list "[g1,g2,...]"
# (matching the format predict_2factor_topt.py emits to fps.g).  Comment
# lines (starting with '#') and blanks are skipped.
MATERIALIZE       := __MATERIALIZE__;
CANDIDATES_PATH   := "__CANDIDATES_PATH__";

Print("wreath: m_src=", M, " d=", DD, " t=", TID,
      " m_blocks=", M_BLOCKS, " target_n=", TARGET_N,
      " materialize=", MATERIALIZE, "\n");

S_M := SymmetricGroup(M);
T_orig := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);

# T-side acts on [M+1..M+D] (last block).
shift := MappingPermListList([1..DD], [M+1..M+DD]);
T := T_orig^shift;
N_T_block := Normalizer(SymmetricGroup([M+1..M+DD]), T);

# Build the wreath ambient W = N_T_canonical wr S_{M_BLOCKS} on [1..TARGET_N].
# WreathProduct(N_T_canonical, S_{m}) acts naturally on M_BLOCKS blocks of
# DD points each via the imprimitive action.  We use the canonical-block
# version (on [1..DD]) and let WreathProduct distribute.
N_T_canonical := Normalizer(S_D, T_orig);
W := WreathProduct(N_T_canonical, SymmetricGroup(M_BLOCKS));
Print("|W|=|N_T wr S_m| = ", Size(W), "\n");

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

# T-side data (only needed when materializing locally via ProcessH).
if MATERIALIZE = 1 then
    T_data := List(Orbits(N_T_block, NormalSubgroups(T), ConjAction),
                   orbit -> rec(K := orbit[1]));
    for r in T_data do
        r.hom := NaturalHomomorphismByNormalSubgroup(T, r.K);
        r.Q := Range(r.hom);
        r.qsize := Size(r.Q);
        r.qid := SafeId(r.Q);
        r.stab := Stabilizer(N_T_block, r.K, ConjAction);
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
fi;

ALL_FP := [];

ProcessH := function(H)
    local N_H, h_normals, eligible, K_H_data, kh_data,
          a_idx, b_idx, isoTH, isos, n_isos, gens_QT, key_of, idx,
          seen, i, j, k, queue, phi, alpha, beta, neighbor, nkey,
          fp, phi_inv, orec;

    N_H := Normalizer(S_M, H);
    h_normals := NormalSubgroups(H);

    # Trivial-quotient direct product
    fp := Group(Concatenation(GeneratorsOfGroup(H), GeneratorsOfGroup(T)));
    Add(ALL_FP, fp);

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

t0 := Runtime();
if MATERIALIZE = 1 then
    for H_idx in [1..Length(SUBGROUPS)] do
        ProcessH(SUBGROUPS[H_idx]);
    od;
else
    # Load pre-materialized candidates from CANDIDATES_PATH.  Each line is
    # either a comment (# ...), blank, or "[g1,g2,...]" with permutations
    # in cycle notation.  EvalString builds the list; Group(list) builds
    # the subgroup.  The empty bracket "[]" denotes the trivial group.
    Print("loading candidates from ", CANDIDATES_PATH, "\n");
    cand_stream := InputTextFile(CANDIDATES_PATH);
    if cand_stream = fail then
        Error("cannot open candidates file: ", CANDIDATES_PATH);
    fi;
    cand_n_lines := 0;
    cand_n_loaded := 0;
    cand_buf := "";
    while not IsEndOfStream(cand_stream) do
        cand_line := ReadLine(cand_stream);
        if cand_line = fail then break; fi;
        cand_line := Chomp(cand_line);
        cand_n_lines := cand_n_lines + 1;
        if Length(cand_line) = 0 then continue; fi;
        if cand_line[1] = '#' then continue; fi;
        # Handle GAP-style backslash-newline continuations: if a line ends
        # with '\', accumulate and continue reading the next line.
        if cand_line[Length(cand_line)] = '\\' then
            Append(cand_buf, cand_line{[1..Length(cand_line)-1]});
            continue;
        fi;
        if Length(cand_buf) > 0 then
            Append(cand_buf, cand_line);
            cand_line := cand_buf;
            cand_buf := "";
        fi;
        cand_gens := EvalString(cand_line);
        if Length(cand_gens) = 0 then
            Add(ALL_FP, Group(()));
        else
            Add(ALL_FP, Group(cand_gens));
        fi;
        cand_n_loaded := cand_n_loaded + 1;
        if cand_n_loaded mod 100000 = 0 then
            Print("  loaded ", cand_n_loaded, " candidates\n");
        fi;
    od;
    CloseStream(cand_stream);
    Print("loaded ", cand_n_loaded, " candidates from ",
          cand_n_lines, " lines\n");
fi;
mat_elapsed := Runtime() - t0;
n_materialized := Length(ALL_FP);
Print("materialized: ", n_materialized, " fp's in ", mat_elapsed, "ms\n");

# RA-dedup in W (the species normalizer N_T wr S_m) with block-aware
# fingerprints.  RA in W uses GAP's partition-backtrack methods and is fast
# *given* small bucket sizes; the key is to bucket by strong block-aware
# invariants before pairwise RA.
t1 := Runtime();

# T_BLOCKS_N_TARGET: per-block T placement on TARGET_N points.
T_blocks_full := List([1..M_BLOCKS],
    bi -> T_orig^MappingPermListList([1..DD], [(bi-1)*DD+1..bi*DD]));
T_m_full := Group(Concatenation(List(T_blocks_full, GeneratorsOfGroup)));
block_pts_list := List([1..M_BLOCKS], bi -> Set([(bi-1)*DD+1..bi*DD]));

# ===================== Tier A: mod-2 abelianization gluing code =====================
# Appends to fp_fingerprint the weight enumerator of H's image in the product of the
# per-block mod-2 abelianizations T/(T'T^2), in CONSISTENT cross-block coordinates
# (one T_orig abelianization transported by the standard block shift, so a W block-swap
# is a clean coordinate-block permutation).  This refinement is W-invariant ONLY when
# N_T acts trivially on T/(T'T^2).  Because this worker is also used as a GENERAL dedup
# check, routing is NOT relied on for safety: the worker verifies it itself and DISABLES
# the key (falling back to the base fingerprint) unless BOTH (1) the WEN_SAFE certificate
# and (2) an empirical conjugation self-check (under the worker's own W) pass.  An unsafe
# key scatters W-conjugates across buckets -> they never meet in within-bucket RA ->
# silent overcount (validation: on V4^3, 109/144 random W-conjugations changed it).
PHI_frat2 := G -> ClosureGroup(DerivedSubgroup(G),
                               Group(List(GeneratorsOfGroup(G), x -> x^2)));
PHI_ab2  := NaturalHomomorphismByNormalSubgroup(T_orig, PHI_frat2(T_orig));
PHI_Q    := Image(PHI_ab2);
if IsTrivial(PHI_Q) then PHI_pcgs := []; PHI_dT := 0;
else PHI_pcgs := Pcgs(PHI_Q); PHI_dT := Length(PHI_pcgs); fi;
PHI_D       := PHI_dT * M_BLOCKS;
PHI_shiftIn := List([1..M_BLOCKS], bi -> MappingPermListList([(bi-1)*DD+1..bi*DD], [1..DD]));
PHI_zero    := Zero(GF(2));
PHI_one     := One(GF(2));

PHI_Vec := function(g)
    local v, bi, telt, e, k;
    v := ListWithIdenticalEntries(PHI_D, PHI_zero);
    for bi in [1..M_BLOCKS] do
        telt := RestrictedPerm(g, block_pts_list[bi]) ^ PHI_shiftIn[bi];
        e := ExponentsOfPcElement(PHI_pcgs, Image(PHI_ab2, telt));
        for k in [1..PHI_dT] do
            if e[k] mod 2 = 1 then v[(bi-1)*PHI_dT+k] := PHI_one; fi;
        od;
    od;
    return v;
end;

PHI_Summary := function(G)
    local vecs, B, dim, bi, proj, wen;
    vecs := List(GeneratorsOfGroup(G), PHI_Vec);
    if vecs = [] then B := []; else B := BaseMat(vecs); fi;
    dim := Length(B);
    proj := SortedList(List([1..M_BLOCKS],
        bi -> RankMat(List(B, v -> v{[(bi-1)*PHI_dT+1..bi*PHI_dT]}))));
    if dim = 0 then wen := [[0, 1]];
    else wen := Collected(List(AsList(VectorSpace(GF(2), B)),
                               v -> Number(v, x -> not IsZero(x)))); fi;
    return [dim, proj, wen];
end;

# Gate 1: WEN_SAFE certificate -- N_T_canonical acts trivially on T/(T'T^2).
PHI_WEN_SAFE := true;
if PHI_dT >= 2 then
    if ForAny(GeneratorsOfGroup(N_T_canonical),
              gg -> ForAny(GeneratorsOfGroup(T_orig),
                           xx -> Image(PHI_ab2, xx^gg) <> Image(PHI_ab2, xx))) then
        PHI_WEN_SAFE := false;
    fi;
fi;

# Gate 2: empirical self-check -- key computes on every materialized input AND is
# invariant under random W-conjugation on a sample.  Wrapped so ANY error disables it.
PHI_validate := function()
    local i, nsamp, H, kk, t, w;
    for i in [1..n_materialized] do PHI_Summary(ALL_FP[i]); od;
    nsamp := Minimum(25, n_materialized);
    for i in [1..nsamp] do
        H := ALL_FP[i]; kk := PHI_Summary(H);
        for t in [1..8] do
            w := PseudoRandom(W);
            if PHI_Summary(H^w) <> kk then return false; fi;
        od;
    od;
    return true;
end;
PHI_ENABLED := false;
if PHI_dT > 0 and PHI_WEN_SAFE and n_materialized > 0 then
    PHI_trial := CALL_WITH_CATCH(PHI_validate, []);
    if PHI_trial[1] = true and PHI_trial[2] = true then PHI_ENABLED := true; fi;
fi;
if __PHI_DISABLE__ = 1 then PHI_ENABLED := false; fi;   # env WREATH_DISABLE_PHI=1 (A/B)
Print("Tier-A Phi gluing code: dT=", PHI_dT, " WEN_SAFE=", PHI_WEN_SAFE,
      " ENABLED=", PHI_ENABLED, "\n");

# ===================== Tier D-lite: canonical form of the abelian gluing code =====
# canonPhi(H) = lex-min over g in W|_{F2^D} of RREF(Basis(Phi(H))*g), where
# W|_{F2^D} = (GL-image of N_T on T/(T'T^2)) wr S_m is the action W induces on the
# PHI coordinates.  W-invariant BY CONSTRUCTION (the lex-min quotients out the GL
# image), so -- unlike the Tier-A weight enumerator -- it needs NO WEN_SAFE gate and
# is safe for V4 / elementary-abelian species (where Tier A self-disables).  It is a
# COMPLETE invariant of the abelian code (strictly finer than the weight enumerator),
# so it collapses each abelian-equivalence bucket to its true W-classes-of-Phi before
# the pairwise RA backstop.  RA stays exact, so a bug here can only OVER-split
# (overcount) -- caught by the same conjugation self-check pattern as Tier A.
# Design note: tier_d_canonical_form.md section 6.
TIERDLITE_ENABLED := false;
TD_GLsize   := 0;
TD_grpOrder := 0;
TD_CAP      := 200000;     # enable only if |GL-image|^m * m! <= TD_CAP (else WEN+RA)
canonPhi    := fail;
if PHI_dT > 0 then
    # GL-image: for each N_T generator, its PHI_dT x PHI_dT GF(2) matrix on the
    # PHI_pcgs basis (row k = exponents of e_k^gg).  Code vectors are ROWS, GL acts
    # on the right (v -> v*M), matching PHI_Vec's exponent storage.
    TD_pcrep := List(PHI_pcgs, p -> PreImagesRepresentative(PHI_ab2, p));
    TD_glMat := function(gg)
        local rows, k;
        rows := [];
        for k in [1..PHI_dT] do
            Add(rows, List(ExponentsOfPcElement(PHI_pcgs,
                              Image(PHI_ab2, TD_pcrep[k]^gg)),
                           e -> (e mod 2) * PHI_one));
        od;
        return rows;
    end;
    TD_glGens := Filtered(List(GeneratorsOfGroup(N_T_canonical), TD_glMat),
                          M -> M <> IdentityMat(PHI_dT, GF(2)));
    if TD_glGens = [] then
        TD_GLelems := [ IdentityMat(PHI_dT, GF(2)) ];   # trivial GL (e.g. D8)
        TD_GLsize  := 1;
    else
        TD_GL      := Group(TD_glGens);
        TD_GLelems := AsList(TD_GL);                    # nontrivial GL (e.g. V4 -> S3)
        TD_GLsize  := Size(TD_GL);
    fi;
    TD_grpOrder := TD_GLsize ^ M_BLOCKS * Factorial(M_BLOCKS);
    TD_glTuples := Cartesian(List([1..M_BLOCKS], i -> TD_GLelems));   # GL-image^m tuples

    TD_rref := function(rows)
        if Length(rows) = 0 then return []; fi;
        return Filtered(TriangulizedMat(rows), r -> not IsZero(r));  # unique RREF
    end;
    # Apply a wreath element (per-block GL tuple glt, block permutation pi) to a basis.
    TD_apply := function(basis, glt, pi)
        local out, v, w, bi, src;
        out := [];
        for v in basis do
            w := ShallowCopy(v);
            for bi in [1..M_BLOCKS] do
                src := bi ^ (pi^-1);
                w{[(bi-1)*PHI_dT+1 .. bi*PHI_dT]} :=
                    v{[(src-1)*PHI_dT+1 .. src*PHI_dT]} * glt[src];
            od;
            Add(out, w);
        od;
        return out;
    end;
    canonPhi := function(G)
        local Bv, B, best, pi, glt, rr, cur;
        Bv := List(GeneratorsOfGroup(G), PHI_Vec);
        if Bv = [] then return [0, []]; fi;
        B := BaseMat(Bv);
        if Length(B) = 0 then return [0, []]; fi;
        best := fail;
        for pi in SymmetricGroup(M_BLOCKS) do
            for glt in TD_glTuples do
                rr := TD_rref(TD_apply(B, glt, pi));
                cur := [Length(rr), List(rr, r -> List(r, IntFFE))];  # hashable key
                if best = fail or cur < best then best := cur; fi;
            od;
        od;
        return best;
    end;

    # Self-check: canonPhi must be stable under random W-conjugation (clone of
    # PHI_validate).  Any error / instability disables the key -> fall back to WEN+RA.
    TD_validate := function()
        local i, nsamp, H, kk, t, w;
        for i in [1..n_materialized] do canonPhi(ALL_FP[i]); od;
        nsamp := Minimum(25, n_materialized);
        for i in [1..nsamp] do
            H := ALL_FP[i]; kk := canonPhi(H);
            for t in [1..8] do
                w := PseudoRandom(W);
                if canonPhi(H^w) <> kk then return false; fi;
            od;
        od;
        return true;
    end;
    if n_materialized > 0 and TD_grpOrder <= TD_CAP then
        TD_trial := CALL_WITH_CATCH(TD_validate, []);
        if TD_trial[1] = true and TD_trial[2] = true then TIERDLITE_ENABLED := true; fi;
    fi;
fi;
if __TIERD_DISABLE__ = 1 then TIERDLITE_ENABLED := false; fi;  # env WREATH_DISABLE_TIERD=1
Print("Tier-D-lite canonPhi: dT=", PHI_dT, " GLsize=", TD_GLsize,
      " grpOrder=", TD_grpOrder, " cap=", TD_CAP,
      " ENABLED=", TIERDLITE_ENABLED, "\n");

# ===================== Tier D (full): complete canonical form under W =============
# PROTOTYPE, gated OFF by default (env WREATH_ENABLE_TIERD_FULL=1).  canonFull(H) is a
# COMPLETE canonical form of H under W: encode H by the index-set of its elements in the
# wreath base B = T^m (|B| = |T|^m), on which W acts by conjugation as a permutation
# group W_perm; canonFull(H) := CanonicalImage(W_perm, idx(H), OnSets) (images package).
# Then H_i ~_W H_j  <=>  canonFull(H_i) = canonFull(H_j), EXACTLY -- so a residual bucket
# resolves in O(b) canon calls + grouping instead of O(b^2) pairwise RA.  Cost scales
# with |T|^m (the doc's old "MinimalImage too slow" result), so it is gated to small
# |B| and applied ONLY to residual buckets >= a threshold; pairwise RA handles the rest.
# Design note: tier_d_canonical_form.md section 3.  Bench-only this round (don't promote).
TIERDFULL_ENABLED   := false;
TIERDFULL_CAP       := 4096;   # |T|^m cap on the conjugation domain
TIERDFULL_THRESHOLD := 8;      # only replace RA on buckets at least this big
canonFull           := fail;
if __TIERDFULL_ENABLE__ = 1 then
    if LoadPackage("images") <> fail and Size(T_m_full) <= TIERDFULL_CAP then
        TDF_Belems := Elements(T_m_full);
        TDF_Bidx   := NewDictionary(TDF_Belems[1], true);
        for tdf_ii in [1..Length(TDF_Belems)] do
            AddDictionary(TDF_Bidx, TDF_Belems[tdf_ii], tdf_ii);
        od;
        TDF_Wperm := Image(ActionHomomorphism(W, TDF_Belems, OnPoints));  # conj action
        canonFull := function(H)
            local idx;
            idx := Set(Elements(H), e -> LookupDictionary(TDF_Bidx, e));
            return CanonicalImage(TDF_Wperm, idx, OnSets);
        end;
        TDF_validate := function()
            local i, nsamp, H, kk, t, w;
            nsamp := Minimum(15, n_materialized);
            for i in [1..nsamp] do
                H := ALL_FP[i]; kk := canonFull(H);
                for t in [1..5] do
                    w := PseudoRandom(W);
                    if canonFull(H^w) <> kk then return false; fi;
                od;
            od;
            return true;
        end;
        if n_materialized > 0 then
            TDF_trial := CALL_WITH_CATCH(TDF_validate, []);
            if TDF_trial[1] = true and TDF_trial[2] = true then TIERDFULL_ENABLED := true; fi;
        fi;
    fi;
fi;
Print("Tier-D-full canonFull: enable_req=", __TIERDFULL_ENABLE__,
      " |B|=", Size(T_m_full), " cap=", TIERDFULL_CAP,
      " thresh=", TIERDFULL_THRESHOLD, " ENABLED=", TIERDFULL_ENABLED, "\n");

fp_fingerprint := function(G)
    local sz, abi, ds, idg, block_perm, pure_F, pure_size, pure_abi,
          per_block_kernel_sizes, subset_dim_signature, k, S, subset_pts,
          gens_S, projG_S, phi_extra;
    sz := Size(G);
    abi := AbelianInvariants(G);
    ds := List(DerivedSeries(G), Size);
    if IdGroupsAvailable(sz) then idg := IdGroup(G); else idg := 0; fi;

    block_perm := Action(G, block_pts_list, OnSets);
    pure_F := Intersection(G, T_m_full);
    pure_size := Size(pure_F);
    pure_abi := AbelianInvariants(pure_F);

    per_block_kernel_sizes := SortedList(List([1..M_BLOCKS], bi ->
        Size(Group(List(GeneratorsOfGroup(pure_F),
            g -> RestrictedPerm(g, [(bi-1)*DD+1..bi*DD])), ()))));

    # Subset-projection signature: for each subset size k=2..M_BLOCKS-1,
    # multiset of |proj_S(pure_F)| over k-subsets S.  S_m-invariant via
    # SortedList.  Cheap (~0.1s for m=6).  Strongly discriminative for
    # subspace structures.
    subset_dim_signature := [];
    for k in [2..M_BLOCKS - 1] do
        Add(subset_dim_signature, SortedList(List(Combinations([1..M_BLOCKS], k),
            function(S)
                local subset_pts, gens_S;
                subset_pts := Concatenation(List(S, bi -> [(bi-1)*DD+1..bi*DD]));
                gens_S := List(GeneratorsOfGroup(pure_F),
                    g -> RestrictedPerm(g, subset_pts));
                return Size(Group(gens_S, ()));
            end)));
    od;

    if   TIERDLITE_ENABLED then phi_extra := canonPhi(G);     # Tier D-lite (complete, always-safe)
    elif PHI_ENABLED       then phi_extra := PHI_Summary(G);  # Tier A (WEN, WEN_SAFE-gated)
    else                        phi_extra := 0;
    fi;
    return [sz, idg, abi, ds,
            Size(block_perm), IdGroup(block_perm),
            pure_size, pure_abi,
            per_block_kernel_sizes,
            subset_dim_signature,
            phi_extra];
end;

# Rich invariants borrowed from lifting_method_fast_v2.g:CheapSubgroupInvariantFull
# + ExpensiveSubgroupInvariant.  Triggered only when the cheap fingerprint leaves
# a bucket with > 1000 predicted RA-call pairs (i.e. size > 45).
fp_fingerprint_rich := function(G)
    local base, sz, moved, derived, derivedSizes, D, nc,
          orderHist, g, o, classes, cl, classHist, cycleType,
          pairs, pairOrbLens, perBlockImg, bi, blockPts;
    base := fp_fingerprint(G);
    sz := Size(G);
    moved := MovedPoints(G);

    Add(base, DerivedLength(G));
    Add(base, Size(Center(G)));
    derived := DerivedSubgroup(G);
    Add(base, Size(derived));
    Add(base, Exponent(G));

    # Derived-series sizes up to depth 6.
    derivedSizes := [sz, Size(derived)];
    D := derived;
    while Size(D) > 1 and Length(derivedSizes) < 6 do
        D := DerivedSubgroup(D);
        Add(derivedSizes, Size(D));
    od;
    Add(base, derivedSizes);

    if IsNilpotentGroup(G) then nc := NilpotencyClassOfGroup(G);
    else nc := -1; fi;
    Add(base, nc);

    # Element-order histogram (gated |G| <= 1e5).
    if sz <= 100000 then
        orderHist := [];
        for g in G do
            o := Order(g);
            if IsBound(orderHist[o]) then
                orderHist[o] := orderHist[o] + 1;
            else
                orderHist[o] := 1;
            fi;
        od;
        Add(base, orderHist);
    else
        Add(base, -1);
    fi;

    # Per-block action-image order.
    perBlockImg := [];
    for bi in [1..M_BLOCKS] do
        blockPts := [(bi-1)*DD+1..bi*DD];
        Add(perBlockImg,
            Size(G) / Size(Stabilizer(G, blockPts, OnTuples)));
    od;
    Sort(perBlockImg);
    Add(base, perBlockImg);

    # CC cycle-type histogram (gated |G| <= 1e4).
    if sz <= 10000 then
        classes := ConjugacyClasses(G);
        classHist := rec();
        for cl in classes do
            cycleType := String(SortedList(CycleLengths(Representative(cl), moved)));
            if IsBound(classHist.(cycleType)) then
                classHist.(cycleType) := classHist.(cycleType) + Size(cl);
            else
                classHist.(cycleType) := Size(cl);
            fi;
        od;
        Add(base, classHist);
    else
        Add(base, -1);
    fi;

    # 2-subset orbit lengths (gated |moved| <= 20).
    if Length(moved) > 0 and Length(moved) <= 20 then
        pairs := Combinations(moved, 2);
        pairOrbLens := SortedList(List(Orbits(G, pairs, OnSets), Length));
        Add(base, pairOrbLens);
    else
        Add(base, -1);
    fi;

    return base;
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

# List-of-buckets to avoid GAP record-name 1023-char cap on long fingerprints.
bucket_keys := [];
bucket_lists := [];
for i in [1..n_materialized] do
    pos := Position(bucket_keys, fps[i]);
    if pos = fail then
        Add(bucket_keys, fps[i]);
        Add(bucket_lists, [i]);
    else
        Add(bucket_lists[pos], i);
    fi;
od;
Print("buckets: ", Length(bucket_lists),
      " (max bucket size: ", Maximum(List(bucket_lists, Length)), ")\n");

# Trigger rich-invariant upgrade for the WHOLE combo when any bucket has
# > 1000 predicted RA-call pairs (size > 45) OR total predicted pairs > 5000.
# Mirrors legacy RICH_DEDUP_THRESHOLD = 1000 from lifting_method_fast_v2.g.
max_bucket_size := Maximum(List(bucket_lists, Length));
total_pred_ra := Sum(bucket_lists, b -> Length(b) * (Length(b) - 1) / 2);
if max_bucket_size > 45 or total_pred_ra > 5000 then
    Print("UPGRADE: max bucket=", max_bucket_size,
          " total_pred_ra=", total_pred_ra,
          " -> recomputing with rich invariants\n");
    t_rich := Runtime();
    fps := List(ALL_FP, fp_fingerprint_rich);
    Print("UPGRADE: rich fingerprints in ", Runtime() - t_rich, "ms\n");
    bucket_keys := [];
    bucket_lists := [];
    for i in [1..n_materialized] do
        pos := Position(bucket_keys, fps[i]);
        if pos = fail then
            Add(bucket_keys, fps[i]);
            Add(bucket_lists, [i]);
        else
            Add(bucket_lists[pos], i);
        fi;
    od;
    Print("UPGRADE: re-bucketed -> ", Length(bucket_lists), " buckets",
          " (max size: ", Maximum(List(bucket_lists, Length)), ",",
          " new total_pred_ra: ",
          Sum(bucket_lists, b -> Length(b) * (Length(b) - 1) / 2), ")\n");
fi;

# Debug: print bucket sizes only (skip key dump for legibility on large buckets)
for b_dbg in [1..Length(bucket_lists)] do
    Print("  bucket ", b_dbg, " size=", Length(bucket_lists[b_dbg]), "\n");
od;

n_conj_pairs := 0;
n_ra_calls := 0;
ra_total_ms := 0;
ra_max_ms := 0;
n_tierdfull_buckets := 0;       # buckets resolved by full Tier D instead of pairwise RA
for b_idx in [1..Length(bucket_lists)] do
    bk := bucket_lists[b_idx];
    bucket_t0 := Runtime();
    bucket_calls := 0;
    if TIERDFULL_ENABLED and Length(bk) >= TIERDFULL_THRESHOLD then
        # Complete canonical form: group bucket members by canonFull, union each group.
        # O(b) canon calls + grouping, no pairwise RA.
        canon_keys := [];
        canon_groups := [];
        for i in bk do
            ck := canonFull(ALL_FP[i]);
            pos := Position(canon_keys, ck);
            if pos = fail then
                Add(canon_keys, ck); Add(canon_groups, [i]);
            else
                Add(canon_groups[pos], i);
            fi;
        od;
        for grp in canon_groups do
            for jj in [2..Length(grp)] do UF_Union(grp[1], grp[jj]); od;
        od;
        n_tierdfull_buckets := n_tierdfull_buckets + 1;
        Print("  bucket ", b_idx, " size=", Length(bk),
              " TIER-D-FULL canon-groups=", Length(canon_groups),
              " elapsed=", Runtime() - bucket_t0, "ms\n");
    else
    for i in [1..Length(bk)-1] do
        for j in [i+1..Length(bk)] do
            if UF_Find(bk[i]) = UF_Find(bk[j]) then continue; fi;
            n_ra_calls := n_ra_calls + 1;
            bucket_calls := bucket_calls + 1;
            ra_t0 := Runtime();
            ra_result := RepresentativeAction(W, ALL_FP[bk[i]], ALL_FP[bk[j]]);
            ra_elapsed := Runtime() - ra_t0;
            ra_total_ms := ra_total_ms + ra_elapsed;
            if ra_elapsed > ra_max_ms then ra_max_ms := ra_elapsed; fi;
            if ra_result <> fail then
                UF_Union(bk[i], bk[j]);
                n_conj_pairs := n_conj_pairs + 1;
            fi;
        od;
    od;
    Print("  bucket ", b_idx, " size=", Length(bk),
          " calls=", bucket_calls,
          " elapsed=", Runtime() - bucket_t0, "ms\n");
    fi;
od;
Print("RA TIMING: total_calls=", n_ra_calls,
      "  total_time=", ra_total_ms, "ms",
      "  avg=", Int(ra_total_ms / Maximum(n_ra_calls, 1)), "ms",
      "  max=", ra_max_ms, "ms",
      "  tierdfull_buckets=", n_tierdfull_buckets, "\n");
classes := Set([1..n_materialized], i -> UF_Find(i));
n_distinct := Length(classes);
ra_elapsed := Runtime() - t1;
Print("RA-in-W dedup: ", n_distinct, " distinct from ", n_materialized,
      " (", n_ra_calls, " RA calls, ", n_conj_pairs, " conj pairs, ",
      ra_elapsed, "ms)\n");

# HARVEST: class_sum per distinct class via labelled_oracle.g
# LocalizedFastClassSize.  Bounded: n_distinct is typically small for wreath
# combos, and the per-rep Normalizer(W, H) runs in a tiny block-wreath W.
Read("C:/Users/jeffr/Downloads/Lifting/labelled_oracle.g");
wreath_cs_sum := 0;
seen_class := rec();
wreath_rep_idxs := [];
for i in [1..n_materialized] do
    cls := UF_Find(i);
    cls_key := String(cls);
    if not IsBound(seen_class.(cls_key)) then
        seen_class.(cls_key) := true;
        Add(wreath_rep_idxs, i);
        wreath_cs_sum := wreath_cs_sum +
            LocalizedFastClassSize(ALL_FP[i], TARGET_N);
    fi;
od;

# Emit one fp generator-list per distinct class (one rep per UF class).
# Output written as raw bracketed lines; Python wrapper composes legacy header.
# First line is the harvest header: `# class_sum: N`.
EMIT_GENS_PATH := "__GEN_PATH__";
if EMIT_GENS_PATH <> "" then
    PrintTo(EMIT_GENS_PATH, "# class_sum: ", wreath_cs_sum, "\n");
    for i in wreath_rep_idxs do
        gens := GeneratorsOfGroup(ALL_FP[i]);
        if Length(gens) > 0 then
            gens_s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            gens_s := "";
        fi;
        AppendTo(EMIT_GENS_PATH, "[", gens_s, "]\n");
    od;
fi;

Print("RESULT n_materialized=", n_materialized,
      " n_distinct=", n_distinct,
      " predicted=", n_distinct,
      " class_sum=", wreath_cs_sum, "\n");
LogTo();
QUIT;
"""


def _format_combo_header(combo):
    """Legacy '# combo:' line.  combo is a list of (d, t) tuples."""
    pairs = ", ".join(f"[ {d}, {t} ]" for d, t in sorted(combo))
    return f"# combo: [ {pairs} ]"


def _join_gap_continuations(raw_lines):
    joined, buf = [], []
    for ln in raw_lines:
        if ln.endswith("\\"):
            buf.append(ln[:-1])
        else:
            buf.append(ln)
            joined.append("".join(buf))
            buf = []
    if buf:
        joined.append("".join(buf))
    return [ln for ln in joined if ln.strip()]


def _write_legacy_format(output_path, combo, raw_gens_lines, deduped_count, elapsed_ms):
    """Atomic write: write to output_path.tmp, then os.replace() to final path.
    Crashes mid-write leave only the .tmp; the final file only appears once
    all gens are flushed."""
    joined_lines = _join_gap_continuations(raw_gens_lines)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(_format_combo_header(combo) + "\n")
        f.write(f"# candidates: {deduped_count}\n")
        f.write(f"# deduped: {deduped_count}\n")
        f.write(f"# elapsed_ms: {elapsed_ms}\n")
        for line in joined_lines:
            f.write(line + "\n")
    os.replace(tmp_path, output_path)   # atomic on POSIX; also atomic on Windows for same volume
    return len(joined_lines)


def predict_wreath(combo_str: str, target_n=18, timeout=3600,
                   emit_generators=False, output_path=None,
                   candidates_from=None):
    """Single-cluster m-block predictor.

    Two materialization modes:
      - Default (candidates_from=None): walk SUBGROUPS = (m-1)-block source and
        Goursat-fuse against the m-th block T to build ALL_FP.
      - candidates_from=<path>: skip the local Goursat and load pre-materialized
        candidates from that file (one bracketed gen list per line, # comments
        skipped, blank lines skipped).  Used by the build-pipeline route that
        first runs predict_2factor_topt's holt_split to generate candidates.
    Bucketize+RA-dedup-in-W is identical in both modes.
    """
    pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
    pairs = pat.findall(combo_str)
    target_combo = tuple(sorted((int(d), int(t)) for d, t in pairs))
    species = set(target_combo)
    if len(species) != 1:
        return {"error": f"not single-cluster: species={species}"}
    d, t = next(iter(species))
    m_blocks = len(target_combo)
    if m_blocks < 2:
        return {"error": "m_blocks must be >= 2"}

    # Source = (m-1) blocks of (d, t).  Only needed when MATERIALIZE=1.
    src_n = (m_blocks - 1) * d
    src_part = "[" + ",".join([str(d)] * (m_blocks - 1)) + "]"
    src_combo = "_".join([f"[{d},{t}]"] * (m_blocks - 1))
    src_file = SN_DIR / str(src_n) / src_part / f"{src_combo}.g"

    target_str = "_".join(f"[{dd},{tt}]" for dd, tt in target_combo)
    work = TMP / target_str
    work.mkdir(parents=True, exist_ok=True)

    materialize = 1 if candidates_from is None else 0
    subs_g = work / "subs.g"
    if materialize == 1:
        if not src_file.exists():
            return {"error": f"source not found: {src_file}"}
        subs = parse_combo_file(src_file)
        if not subs:
            return {"error": "empty source"}
        with open(subs_g, "w") as f:
            f.write("SUBGROUPS := [\n")
            for i, s in enumerate(subs):
                sep = "," if i < len(subs) - 1 else ""
                f.write(f"  Group({s}){sep}\n")
            f.write("];\n")
    else:
        # Sentinel; GAP path is gated on MATERIALIZE.
        subs_g.write_text("# unused: candidates loaded from CANDIDATES_PATH\n",
                          encoding="utf-8")
        cand_path = Path(candidates_from)
        if not cand_path.exists():
            return {"error": f"candidates file not found: {cand_path}"}

    log = work / "wreath.log"
    if log.exists(): log.unlink()
    if output_path is not None:
        emit_generators = True
    # When loading candidates from disk (candidates_from), the candidates
    # file itself is typically <work>/fps.g (since predict_2factor_topt's
    # default emit path collides with ours).  Use a distinct output filename
    # so we don't trample the input.
    out_gens_name = "deduped_gens.g" if candidates_from else "fps.g"
    gen_path = (work / out_gens_name) if emit_generators else None
    if gen_path is not None and gen_path.exists(): gen_path.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_WREATH
        .replace("__LOG__", to_cyg(log))
        .replace("__M__", str(src_n))
        .replace("__D__", str(d))
        .replace("__T_ID__", str(t))
        .replace("__M_BLOCKS__", str(m_blocks))
        .replace("__SUBS_CYG__", to_cyg(subs_g))
        .replace("__PHI_DISABLE__", os.environ.get("WREATH_DISABLE_PHI", "0"))
        .replace("__TIERD_DISABLE__", os.environ.get("WREATH_DISABLE_TIERD", "0"))
        .replace("__TIERDFULL_ENABLE__", os.environ.get("WREATH_ENABLE_TIERD_FULL", "0"))
        .replace("__MATERIALIZE__", str(materialize))
        .replace("__CANDIDATES_PATH__",
                 to_cyg(Path(candidates_from)) if candidates_from else "")
        .replace("__GEN_PATH__", to_cyg(gen_path) if gen_path else ""),
        encoding="utf-8",
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # timeout >= 30 days OR <= 0 means "no timeout" (avoid threading.Lock overflow on Windows).
    sub_timeout = None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30) else timeout
    try:
        if sub_timeout is None:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"RESULT n_materialized=\s*(\d+)\s+n_distinct=\s*(\d+)\s+predicted=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT",
                "log_tail": log_text[-2000:],
                "gap_rc": proc.returncode,
                "gap_stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
                "gap_stdout_tail": proc.stdout[-1500:] if proc.stdout else "",
                "elapsed_s": elapsed}
    out = {
        "combo": target_str,
        "d": d, "t": t, "m_blocks": m_blocks,
        "src_n": src_n,
        "n_materialized": int(m.group(1)),
        "n_distinct": int(m.group(2)),
        "predicted": int(m.group(3)),
        "elapsed_s": elapsed,
    }
    if emit_generators and gen_path:
        out["generators_file"] = str(gen_path)
    if output_path is not None and gen_path is not None and gen_path.exists():
        raw_lines = gen_path.read_text(encoding="utf-8").splitlines()
        elapsed_ms = int(elapsed * 1000)
        n_written = _write_legacy_format(Path(output_path), target_combo, raw_lines,
                                          out["predicted"], elapsed_ms)
        if n_written != out["predicted"]:
            out["warning_count_mismatch"] = (
                f"wrote {n_written} generator lines but predicted={out['predicted']}")
        out["output_path"] = str(output_path)
    (work / "result.json").write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--target-n", type=int, default=18)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--emit-generators", action="store_true")
    ap.add_argument("--output-path",
                    help="write legacy-format combo file here (implies --emit-generators)")
    ap.add_argument("--candidates-from",
                    help="path to a fps.g file of pre-materialized candidate "
                         "subgroups (one bracketed gen list per line); when "
                         "set, skips the local Goursat materialization step "
                         "and feeds these candidates directly into bucketize "
                         "+ RA-in-W dedup")
    args = ap.parse_args()
    print(json.dumps(predict_wreath(args.combo, args.target_n, args.timeout,
                                     emit_generators=args.emit_generators,
                                     output_path=args.output_path,
                                     candidates_from=args.candidates_from), indent=2))


if __name__ == "__main__":
    main()
