# prototype_stage_d.g
#
# Stage D: linear/structured kernel-orbit enumeration for the O_p-split glue
# quotients that dominate H-cache build time (2026-06-09 profiling of the
# fresh_0604 n=21 run: [48,48]=C2xS4 75ks, [12,4]=D12 54ks, [24,12]=S4 16ks,
# [36,10]=S3xS3 11ks, [12,3]=A4 7ks, ... of 319ks total >=100ms enum calls).
#
# Family: Q with O_p(Q) elementary abelian = C_p^r (1 <= r <= 4, p in
# {2,3,5}) and top T = Q/O_p(Q) in the already-supported outer set
# {C_2, V_4, C_2^3, C_3, C_3^2, S_3, D_8}.  For K ◁ H with H/K ≅ Q:
#
#   L := preimage of O_p(H/K)  — canonical from K (O_p is characteristic),
#        H/L ≅ T, L/K ≅ C_p^r, K ⊇ Φ := L'·L^p.
#
#   Outer layer: T-kernel orbits of N_H on H — Stage A (Cpa) / B (D8) /
#        C (S3), each rec carrying Stab_NH(L) generators + size.
#   Inner layer: codim-r H-submodules W = K/Φ of B := L/Φ over GF(p).
#        Enumerated NOT by filtering all codim-r subspaces (Gaussian-binomial
#        blowup for r>=2, d>=8) but as kernels of surjective H-module maps
#        F : B -> M, where M = O_p(Q) carries the H-action through
#        H -> H/L -> T_can -> Aut(T)-twist -> conj action on O_p(Q).  All
#        isos H/L -> T are covered by composing one IsomorphismGroups result
#        with every element of Aut(T) (module structures deduped first).
#        The intertwiner space {F : rho_B(h)·F = F·rho_M(h) for all h} is a
#        linear solve (dr <= ~48 unknowns); its elements are enumerated when
#        p^dim <= STAGE_D_HOM_GUARD, else the target falls back to legacy.
#   Iso filter: IdGroup(H/K) = target id — separates extension types sharing
#        the same module data (e.g. C2xS4 vs other (V4+triv)-by-S3
#        extensions).  All table targets have IdGroup-safe orders (<= 216).
#
#   Correctness of the orbit bookkeeping (same argument as Stage C):
#   any normal p-subgroup L/K of H/K ≅ Q of order p^r = |O_p(Q)| equals
#   O_p(H/K), so L is determined by K; hence (a) every valid K appears under
#   exactly one outer L-orbit (no cross-L double count), and (b) any n in
#   N_H normalizing K normalizes L, so Stab_NH(K) <= Stab_NH(L) = S and
#   inner S-orbits/stabilizers give exactly the N_H data.
#
# Exports:
#   STAGE_D_TABLE, StageDEntryForQid(qid)
#   LinearOrbitRecsStageDMulti(H, N_H, jobs)
#       jobs = list of rec(Q := <group>, entry := <table rec>)
#       -> rec(recs := [orbit recs], legacy := [Q's that hit a guard])
#   GroundTruthStageDOrbits(H, N_H, sz, k) / CompareStageDWithGroundTruth
#
# Orbit recs match Stage A/B/C shape exactly:
#   rec(K_H_gens, Stab_NH_KH_gens, Stab_NH_KH_size, qid, qsize)

if not IsBound(LinearOrbitRecsCpa) then
    Print("Need Stage A loaded; reading prototype_stage_a.g\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
fi;
if not IsBound(StabActionOnB) then
    Print("Need Stage B loaded; reading prototype_stage_b.g\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
fi;
if not IsBound(OrdinaryPFrattiniModuleData) then
    Print("Need Stage C loaded; reading prototype_stage_c.g\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_c.g");
fi;

# Enumerating more than this many intertwiner-space elements per module
# structure falls the target back to legacy (marker [stage_d/guard]).
if not IsBound(STAGE_D_HOM_GUARD) then
    STAGE_D_HOM_GUARD := 4096;
fi;

# Target table.  top tags name the outer T-kernel enumerator:
#   C2->Cpa(2,1)  V4->Cpa(2,2)  C2_3->Cpa(2,3)  C3->Cpa(3,1)  C3_2->Cpa(3,2)
#   S3->LinearOrbitRecsS3  D8->LinearOrbitRecsD8
# Each entry: p^r * |T| = sz always.  Selection from the 2026-06-09
# enum-cost ranking (fresh_0604 logs): every target burned >=100s of
# slow-call time, or is a cheap sibling sharing an outer layer.
STAGE_D_TABLE := [
    rec(sz :=  12, k :=  4, p := 3, r := 1, top := "V4"  ),  # D12 = S3xC2
    rec(sz :=  48, k := 48, p := 2, r := 3, top := "S3"  ),  # C2xS4
    rec(sz :=  24, k := 12, p := 2, r := 2, top := "S3"  ),  # S4
    rec(sz :=  36, k := 10, p := 3, r := 2, top := "V4"  ),  # S3xS3
    rec(sz :=  12, k :=  3, p := 2, r := 2, top := "C3"  ),  # A4
    rec(sz :=  24, k := 13, p := 2, r := 3, top := "C3"  ),  # C2xA4
    rec(sz :=  24, k := 14, p := 3, r := 1, top := "C2_3"),  # C2xC2xS3
    rec(sz :=  18, k :=  3, p := 3, r := 2, top := "C2"  ),  # C3xS3
    rec(sz :=  18, k :=  4, p := 3, r := 2, top := "C2"  ),  # (C3xC3):C2
    rec(sz :=  54, k := 14, p := 3, r := 3, top := "C2"  ),  # (C3^3):C2
    rec(sz :=  72, k := 40, p := 3, r := 2, top := "D8"  ),  # (S3xS3):C2
    rec(sz :=  72, k := 46, p := 3, r := 2, top := "C2_3"),  # C2xS3xS3
    rec(sz :=  72, k := 23, p := 3, r := 2, top := "D8"  ),  # (C6xS3):C2
    rec(sz :=  96, k := 227, p := 2, r := 4, top := "S3" ),  # (C2^4:C3):C2
    rec(sz :=  96, k := 226, p := 2, r := 4, top := "S3" ),  # C2^2xS4
    rec(sz := 216, k := 162, p := 3, r := 3, top := "C2_3"), # S3xS3xS3
    rec(sz :=  48, k := 50, p := 2, r := 4, top := "C3"  ),  # C2^4:C3
    rec(sz := 108, k := 39, p := 3, r := 3, top := "V4"  ),  # ((C3xC3):C2)xS3
    rec(sz :=  10, k :=  1, p := 5, r := 1, top := "C2"  ),  # D10
    rec(sz :=  24, k :=  6, p := 3, r := 1, top := "D8"  ),  # D24
    rec(sz :=  24, k :=  8, p := 3, r := 1, top := "D8"  ),  # (C6xC2):C2
    rec(sz :=  36, k := 11, p := 2, r := 2, top := "C3_2"),  # C3xA4
    rec(sz :=  36, k := 12, p := 3, r := 2, top := "V4"  ),  # C6xS3
    rec(sz :=  36, k := 13, p := 3, r := 2, top := "V4"  ),  # C2x((C3xC3):C2)
];

# qid is the production SafeId form [size, 0, [size, k]] (safe ids only —
# every table order is IdGroup-classifiable).
StageDEntryForQid := function(qid)
    local e;
    if Length(qid) <> 3 or qid[2] <> 0 then return fail; fi;
    for e in STAGE_D_TABLE do
        if qid[1] = e.sz and qid[3] = [e.sz, e.k] then return e; fi;
    od;
    return fail;
end;

# ---- canonical top groups (ONE group object per tag, so layer-level iso
# memos are shared safely across sibling targets, e.g. [18,3]/[18,4]) ----
STAGE_D_TOP_CANON := rec();
StageDTopCanon := function(top)
    local tid, T;
    if IsBound(STAGE_D_TOP_CANON.(top)) then
        return STAGE_D_TOP_CANON.(top);
    fi;
    if top = "C2" then tid := [2, 1];
    elif top = "V4" then tid := [4, 2];
    elif top = "C2_3" then tid := [8, 5];
    elif top = "C3" then tid := [3, 1];
    elif top = "C3_2" then tid := [9, 2];
    elif top = "S3" then tid := [6, 1];
    elif top = "D8" then tid := [8, 3];
    else Error("[stage_d] unknown top tag ", top);
    fi;
    T := SmallGroup(tid[1], tid[2]);
    STAGE_D_TOP_CANON.(top) := rec(T := T, elts := Elements(T));
    return STAGE_D_TOP_CANON.(top);
end;

# ---- per-target static data (memoized): twist matrix tables indexed by
# the canonical top's element list ----
STAGE_D_TARGET_CACHE := rec();

# Matrix (right-action convention, M_{gh} = M_g·M_h — matches
# NHActionOnElemAb/StabActionOnB: row j = exponents of pcgsP[j]^q) of
# conjugation by q on P, in pcgsP coordinates over GF(p).
_StageD_ConjMatOnP := function(q, pcgsP, r, p)
    local M, j;
    M := [];
    for j in [1..r] do
        Add(M, ExponentsOfPcElement(pcgsP, pcgsP[j]^q) * One(GF(p)));
    od;
    return M;
end;

StageDTargetData := function(e)
    local key, Q, P, pcgsP, homT, T, autT, tcan, isoTC, twists, seen, a,
        mats, tc, t, lift;
    key := Concatenation("q", String(e.sz), "_", String(e.k));
    if IsBound(STAGE_D_TARGET_CACHE.(key)) then
        return STAGE_D_TARGET_CACHE.(key);
    fi;
    Q := SmallGroup(e.sz, e.k);
    P := PCore(Q, e.p);
    if Size(P) <> e.p ^ e.r or not IsElementaryAbelian(P) then
        Error("[stage_d] table entry [", e.sz, ",", e.k,
              "] does not match O_p structure");
    fi;
    pcgsP := Pcgs(P);
    homT := NaturalHomomorphismByNormalSubgroup(Q, P);
    T := Image(homT);
    tcan := StageDTopCanon(e.top);
    isoTC := IsomorphismGroups(T, tcan.T);
    if isoTC = fail then
        Error("[stage_d] top of [", e.sz, ",", e.k,
              "] is not iso to canonical ", e.top);
    fi;
    autT := AutomorphismGroup(T);
    # For each Aut(T)-twist a, the module structure on M = P indexed by the
    # CANONICAL top's elements: tcan.elts[i] acts by the conj matrix of a
    # lift of a(isoTC^-1(tcan.elts[i])).  As a ranges over Aut(T),
    # a∘isoTC^-1 ranges over ALL isos T_can -> T, covering every
    # identification freedom.  Twists with identical matrix lists induce the
    # same intertwiner equations — dedup now.
    twists := [];
    seen := [];
    for a in Elements(autT) do
        mats := [];
        for tc in tcan.elts do
            t := PreImagesRepresentative(isoTC, tc);
            lift := PreImagesRepresentative(homT, Image(a, t));
            Add(mats, _StageD_ConjMatOnP(lift, pcgsP, e.r, e.p));
        od;
        if not (mats in seen) then
            Add(seen, mats);
            Add(twists, mats);
        fi;
    od;
    STAGE_D_TARGET_CACHE.(key) := rec(
        entry := e, tcan := tcan, twists := twists,
        target_id := [e.sz, e.k],
        qid := [e.sz, 0, [e.sz, e.k]]);
    return STAGE_D_TARGET_CACHE.(key);
end;

# ---- linear algebra: basis of {F (d x r over GF(p)) : A_i·F = F·B_i} ----
_StageD_IntertwinerBasis := function(Amats, Bmats, d, r, p)
    local rows, i, j, k, E, row, ns, idx;
    rows := [];
    for j in [1..d] do
        for k in [1..r] do
            row := [];
            for i in [1..Length(Amats)] do
                # image of basis matrix E_{jk} under X -> A_i·X − X·B_i,
                # flattened row-major ((j,k) -> (j-1)r + k):
                # (A_i·E_jk)[u][k] = A_i[u][j];  (E_jk·B_i)[j][k'] = B_i[k][k'].
                E := NullMat(d, r, GF(p));
                for idx in [1..d] do
                    E[idx][k] := E[idx][k] + Amats[i][idx][j];
                od;
                for idx in [1..r] do
                    E[j][idx] := E[j][idx] - Bmats[i][k][idx];
                od;
                Append(row, Concatenation(E));
            od;
            Add(rows, row);
        od;
    od;
    ns := NullspaceMat(rows);
    return List(ns, function(v)
        local Fm, j2;
        Fm := [];
        for j2 in [1..d] do
            Add(Fm, v{[(j2-1)*r + 1 .. j2*r]});
        od;
        return Fm;
    end);
end;

# ---- the engine ----
# jobs: list of rec(Q := <group object from q_groups>, entry := <table rec>).
# Returns rec(recs := <orbit recs>, legacy := <Q objects to re-run legacy>).
LinearOrbitRecsStageDMulti := function(H, N_H, jobs)
    local out, legacy, outer_memo, layer_memo, job, e, td, top_key, lay_key,
        outer_recs, layers, lay, recs_target, W_batch, W_all, tw, hom_basis,
        h_dim, n_el, coeffs, F, W, W_can, K_gens_in_L, K, v, b_elem, valid,
        mats, Sgrp, orbits, orb, W_rep, stab_S, safe_act_subsp_b,
        lift_act_B, t0, guard_hit, Hgens, Bmats, i, q_img, orec;
    out := [];
    legacy := [];
    outer_memo := rec();
    layer_memo := rec();
    Hgens := GeneratorsOfGroup(H);

    safe_act_subsp_b := function(W2, mat)
        if Length(W2) = 0 then return W2; fi;
        return OnSubspacesByCanonicalBasis(W2, mat);
    end;

    for job in jobs do
        e := job.entry;
        t0 := Runtime();
        if Size(H) mod e.sz <> 0 then continue; fi;
        td := StageDTargetData(e);

        # ---- outer layer (memoized per top tag) ----
        top_key := e.top;
        if not IsBound(outer_memo.(top_key)) then
            if e.top = "C2" then
                outer_memo.(top_key) := LinearOrbitRecsCpa(H, N_H, 2, 1);
            elif e.top = "V4" then
                outer_memo.(top_key) := LinearOrbitRecsCpa(H, N_H, 2, 2);
            elif e.top = "C2_3" then
                outer_memo.(top_key) := LinearOrbitRecsCpa(H, N_H, 2, 3);
            elif e.top = "C3" then
                outer_memo.(top_key) := LinearOrbitRecsCpa(H, N_H, 3, 1);
            elif e.top = "C3_2" then
                outer_memo.(top_key) := LinearOrbitRecsCpa(H, N_H, 3, 2);
            elif e.top = "S3" then
                outer_memo.(top_key) := LinearOrbitRecsS3(H, N_H);
            elif e.top = "D8" then
                outer_memo.(top_key) := LinearOrbitRecsD8(H, N_H);
            else
                Error("[stage_d] unknown top tag ", e.top);
            fi;
        fi;
        outer_recs := outer_memo.(top_key);

        # ---- per-(top, p) layer data (memoized): L, S = Stab_NH(L),
        # B = L/(L'L^p) with H-action matrices, H/L, iso H/L -> T_can ----
        lay_key := Concatenation(top_key, "_p", String(e.p));
        if not IsBound(layer_memo.(lay_key)) then
            layers := [];
            for orec in outer_recs do
                lay := rec(
                    L := SubgroupNC(H, orec.K_H_gens),
                    S := SubgroupNC(N_H, orec.Stab_NH_KH_gens),
                    S_size := orec.Stab_NH_KH_size);
                lay.BL := OrdinaryPFrattiniModuleData(H, lay.L, e.p);
                if lay.BL.d > 0 then
                    lay.NHL_gens := GeneratorsOfGroup(lay.BL.NHL);
                    lay.Hact := StabActionOnB(H, lay.BL.hom_to_B,
                                              lay.BL.pcgs, lay.BL.d, e.p).mats;
                    lay.homL := NaturalHomomorphismByNormalSubgroup(H, lay.L);
                    # iso H/L -> canonical top (exists by the outer stage's
                    # own quotient-type guarantee; defensive fail check).
                    lay.isoTC := IsomorphismGroups(Image(lay.homL),
                                                   td.tcan.T);
                fi;
                Add(layers, lay);
            od;
            layer_memo.(lay_key) := layers;
        fi;
        layers := layer_memo.(lay_key);

        recs_target := [];
        guard_hit := false;
        for lay in layers do
            if guard_hit then break; fi;
            if lay.BL.d < e.r then continue; fi;
            if lay.isoTC = fail then continue; fi;

            # ---- inner layer: kernels of surjective intertwiners B -> M ----
            W_batch := [];
            for tw in td.twists do
                # H-action on M per H generator: index the canonical-top
                # element of h, look up its twist matrix.
                Bmats := [];
                for i in [1..Length(Hgens)] do
                    q_img := Image(lay.isoTC, Image(lay.homL, Hgens[i]));
                    Add(Bmats, tw[Position(td.tcan.elts, q_img)]);
                od;
                hom_basis := _StageD_IntertwinerBasis(
                    lay.Hact, Bmats, lay.BL.d, e.r, e.p);
                h_dim := Length(hom_basis);
                if h_dim = 0 then continue; fi;
                n_el := e.p ^ h_dim;
                if n_el > STAGE_D_HOM_GUARD then
                    Print("    [stage_d/guard] |H|=", Size(H), " Q=[", e.sz,
                          ",", e.k, "] hom_dim=", h_dim, " p=", e.p,
                          " -> legacy\n");
                    guard_hit := true;
                    break;
                fi;
                for coeffs in Tuples(AsList(GF(e.p)), h_dim) do
                    F := coeffs[1] * hom_basis[1];
                    for i in [2..h_dim] do
                        F := F + coeffs[i] * hom_basis[i];
                    od;
                    if RankMat(F) = e.r then
                        W := NullspaceMat(F);
                        if Length(W) = 0 then
                            W_can := [];
                        else
                            W_can := TriangulizedMat(List(W, ShallowCopy));
                        fi;
                        Add(W_batch, W_can);
                    fi;
                od;
            od;
            if guard_hit then break; fi;
            W_all := Set(W_batch);
            if Length(W_all) = 0 then continue; fi;

            # ---- exact iso filter (extension type) ----
            valid := [];
            for W in W_all do
                K_gens_in_L := [];
                for v in W do
                    b_elem := Product(List([1..lay.BL.d],
                        i -> lay.BL.pcgs[i] ^ IntFFE(v[i])));
                    Add(K_gens_in_L,
                        PreImagesRepresentative(lay.BL.hom_to_B, b_elem));
                od;
                K := SubgroupNC(H, Concatenation(lay.NHL_gens, K_gens_in_L));
                if IdGroup(FactorGroupNC(H, K)) = td.target_id then
                    Add(valid, W);
                fi;
            od;
            if Length(valid) = 0 then continue; fi;

            # ---- inner orbits under S = Stab_NH(L) ----
            lift_act_B := function(W2, n)
                local Mn, j, b, l, nl, exp;
                Mn := [];
                for j in [1..lay.BL.d] do
                    b := lay.BL.pcgs[j];
                    l := PreImagesRepresentative(lay.BL.hom_to_B, b);
                    nl := n^-1 * l * n;
                    exp := ExponentsOfPcElement(lay.BL.pcgs,
                                                Image(lay.BL.hom_to_B, nl));
                    Add(Mn, exp * One(GF(e.p)));
                od;
                if Length(W2) = 0 then return W2; fi;
                return OnSubspacesByCanonicalBasis(W2, Mn);
            end;

            mats := StabActionOnB(lay.S, lay.BL.hom_to_B, lay.BL.pcgs,
                                  lay.BL.d, e.p).mats;
            if Length(mats) = 0 then
                orbits := List(valid, W2 -> [W2]);
            else
                Sgrp := Group(mats);
                orbits := OrbitsDomain(Sgrp, valid, safe_act_subsp_b);
            fi;

            for orb in orbits do
                W_rep := orb[1];
                K_gens_in_L := [];
                for v in W_rep do
                    b_elem := Product(List([1..lay.BL.d],
                        i -> lay.BL.pcgs[i] ^ IntFFE(v[i])));
                    Add(K_gens_in_L,
                        PreImagesRepresentative(lay.BL.hom_to_B, b_elem));
                od;
                K := SubgroupNC(H, Concatenation(lay.NHL_gens, K_gens_in_L));
                if Length(mats) = 0 then
                    stab_S := lay.S;
                else
                    stab_S := Stabilizer(lay.S, W_rep, lift_act_B);
                fi;
                Add(recs_target, rec(
                    K_H_gens := GeneratorsOfGroup(K),
                    Stab_NH_KH_gens := GeneratorsOfGroup(stab_S),
                    # Stab_NH(K) <= Stab_NH(L) = S since L = preimage of
                    # O_p(H/K) is canonical from K; within S it is the inner
                    # W-stabilizer.  |Stab| = |S| / |inner orbit|.
                    Stab_NH_KH_size := lay.S_size / Length(orb),
                    qid := td.qid,
                    qsize := e.sz));
            od;
        od;

        if guard_hit then
            Add(legacy, job.Q);
        else
            Append(out, recs_target);
            if Runtime() - t0 >= 100 then
                Print("    [stage_d] |H|=", Size(H), " Q=[", e.sz, ",", e.k,
                      "] -> ", Length(recs_target), " orbits in ",
                      Runtime() - t0, "ms\n");
            fi;
        fi;
    od;
    return rec(recs := out, legacy := legacy);
end;

# Convenience single-target wrapper (validation / ad-hoc use).
LinearOrbitRecsStageD := function(H, N_H, sz, k)
    local e, res;
    e := StageDEntryForQid([sz, 0, [sz, k]]);
    if e = fail then
        Error("[stage_d] no table entry for [", sz, ",", k, "]");
    fi;
    res := LinearOrbitRecsStageDMulti(H, N_H,
        [rec(Q := SmallGroup(sz, k), entry := e)]);
    if Length(res.legacy) > 0 then return fail; fi;
    return res.recs;
end;

# ---- ground truth + comparator (reuses Stage C's generic oracle) ----
GroundTruthStageDOrbits := function(H, N_H, sz, k)
    return _StageC_GroundTruthOrbits(H, N_H, sz, [sz, k]);
end;

CompareStageDWithGroundTruth := function(H, N_H, sz, k)
    local lin, truth;
    lin := LinearOrbitRecsStageD(H, N_H, sz, k);
    if lin = fail then
        return rec(ok := fail, n_linear := -1, n_truth := -1,
                   stab_sizes_linear := [], stab_sizes_truth := []);
    fi;
    truth := GroundTruthStageDOrbits(H, N_H, sz, k);
    return _StageC_Compare(lin, truth);
end;

Print("prototype_stage_d.g loaded (", Length(STAGE_D_TABLE), " targets, ",
      "hom guard ", STAGE_D_HOM_GUARD, ").\n");
