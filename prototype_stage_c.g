# prototype_stage_c.g
#
# Stage C: Linear orbits on C_3 and S_3 (= SmallGroup(6,1)) kernels.
#
#   C_3 (qid [3,0,[3,1]]): elementary abelian rank 1 over GF(3).  Handled
#       directly by Stage A's LinearOrbitRecsCpa(H, N_H, 3, 1); no new code
#       needed here beyond the validation helpers.
#
#   S_3 (qid [6,0,[6,1]]): two-layer, modeled on Stage B's D_8 path.
#       Chief series 1 < C_3 < S_3.  For K ◁ H with H/K ≅ S_3, let L be the
#       preimage of C_3 ◁ S_3.  Then H/L ≅ C_2 and L/K ≅ C_3.
#
#         Outer layer: C_2-kernel L of H.  Stage A enumerates these via
#                      LinearOrbitRecsCpa(H, N_H, 2, 1).
#         Inner layer: codim-1 subspaces of the ORDINARY 3-Frattini quotient
#                      B = L / (L' · L^3).
#
#   CRITICAL difference from D_8: D_8's inner C_2 is central, so Stage B uses
#   the RELATIVE Frattini quotient L/([H,L]·L^p) (which kills [H,L] and makes
#   every hyperplane give an automatically normal K).  S_3's inner C_3 is NOT
#   central — the outer C_2 acts by inversion — so [H,L] ⊄ K.  We therefore
#   use the ORDINARY Frattini quotient L/(L'·L^3) and add an explicit
#   H-invariance filter on hyperplanes (Phi = L'·L^3 is characteristic in L
#   and L ◁ H, so Phi ◁ H, and K ◁ H ⟺ K/Phi is H-invariant in B).  The
#   final IdGroup(H/K) = [6,1] filter separates S_3 from C_6 ([6,2]).
#
# Reuses Stage B helpers as-is (per design): StabActionOnB (called with H for
# the invariance matrices, and with Stab_NH(L) for orbiting), OrbitsDomain +
# a local safe_act wrapper, and _StageB_InducedAutoGens.  Same right-action
# convention (inverse conjugation, n^-1 * x * n) as Stages A and B.
#
# Exports:
#   OrdinaryPFrattiniModuleData(H, L, p) -> rec(NHL, hom_to_B, B, pcgs, d)
#   LinearOrbitRecsS3(H, N_H)     -> [ rec(K_H_gens, Stab_NH_KH_gens, qid, qsize) ]
#   LinearOrbitRecsS3Rich(H, N_H) -> + hom, Q, A_gens
#   GroundTruthS3Orbits(H, N_H), CompareS3WithGroundTruth(H, N_H)
#   GroundTruthC3Orbits(H, N_H),  CompareC3WithGroundTruth(H, N_H)

if not IsBound(LinearOrbitRecsCpa) then
    Print("Need Stage A loaded; reading prototype_stage_a.g\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
fi;
if not IsBound(StabActionOnB) then
    Print("Need Stage B loaded; reading prototype_stage_b.g\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
fi;


# B = L / (L' · L^p) — the ORDINARY p-Frattini quotient of L (NOT the
# relative quotient used by RelFrattiniData).  Field names match
# RelFrattiniData so the orbiting/lift code can mirror LinearOrbitRecsD8.
# Phi = L'·L^p is characteristic in L; since L ◁ H, Phi ◁ H.
OrdinaryPFrattiniModuleData := function(H, L, p)
    local L_pows, Phi, hom_to_B, B, pcgs_B, dB;
    L_pows := SubgroupNC(L, List(GeneratorsOfGroup(L), g -> g^p));
    Phi := ClosureGroup(DerivedSubgroup(L), L_pows);
    hom_to_B := NaturalHomomorphismByNormalSubgroup(L, Phi);
    B := Image(hom_to_B);
    if Size(B) = 1 then
        return rec(NHL := Phi, hom_to_B := hom_to_B, B := B,
                   pcgs := [], d := 0);
    fi;
    pcgs_B := Pcgs(B);
    dB := Length(pcgs_B);
    return rec(NHL := Phi, hom_to_B := hom_to_B, B := B,
               pcgs := pcgs_B, d := dB);
end;


# Stage C main: enumerate S_3-kernel orbits of N_H acting on H.
LinearOrbitRecsS3 := function(H, N_H)
    local recs, c2_recs, c2_rec, L, S, BL, NHL_gens, V, all_hps,
          safe_act_subsp_b, H_action, H_mats, hp_invariant, s3_canonicals,
          hp, K_gens_in_L, K, action, mats, Sgrp, lift_act_B, orbits, orb,
          W_rep, stab_S, v, b_elem, qid, qsize;
    qsize := 6;
    qid := [6, 0, [6, 1]];   # S_3 SafeId
    recs := [];

    # Wrapper around OnSubspacesByCanonicalBasis handling the empty-subspace
    # (codim = dim B) case, where GAP's builtin errors.  Used for both the
    # invariance test and the orbit action.
    safe_act_subsp_b := function(W, mat)
        if Length(W) = 0 then return W; fi;
        return OnSubspacesByCanonicalBasis(W, mat);
    end;

    # Outer layer: C_2-kernels L of H (H/L ≅ C_2).
    c2_recs := LinearOrbitRecsCpa(H, N_H, 2, 1);

    for c2_rec in c2_recs do
        L := SubgroupNC(H, c2_rec.K_H_gens);
        S := SubgroupNC(N_H, c2_rec.Stab_NH_KH_gens);

        # Inner module: ordinary 3-Frattini quotient B = L/(L'·L^3).
        BL := OrdinaryPFrattiniModuleData(H, L, 3);
        if BL.d = 0 then continue; fi;
        NHL_gens := GeneratorsOfGroup(BL.NHL);
        V := GF(3) ^ BL.d;

        # H-action matrices on B (reuse Stage B's StabActionOnB with S := H).
        # Needed to filter hyperplanes to those giving K ◁ H.
        H_action := StabActionOnB(H, BL.hom_to_B, BL.pcgs, BL.d, 3);
        H_mats := H_action.mats;

        # Canonical forms of all codim-1 subspaces (hyperplanes) of B.
        all_hps := List(Subspaces(V, BL.d - 1), function(s)
            local bv;
            bv := BasisVectors(Basis(s));
            if Length(bv) = 0 then return []; fi;
            return TriangulizedMat(List(bv, ShallowCopy));
        end);

        # Keep hyperplanes that are (a) H-invariant -> K ◁ H, and (b) give
        # H/K ≅ S_3 (drops C_6 quotients).  Invariance MUST be checked first:
        # FactorGroupNC requires a normal K.
        s3_canonicals := [];
        for hp in all_hps do
            hp_invariant := ForAll(H_mats, M -> safe_act_subsp_b(hp, M) = hp);
            if not hp_invariant then continue; fi;
            K_gens_in_L := [];
            for v in hp do
                b_elem := Product(List([1..BL.d],
                    i -> BL.pcgs[i] ^ IntFFE(v[i])));
                Add(K_gens_in_L, PreImagesRepresentative(BL.hom_to_B, b_elem));
            od;
            K := SubgroupNC(H, Concatenation(NHL_gens, K_gens_in_L));
            if IdGroup(FactorGroupNC(H, K)) = [6, 1] then
                Add(s3_canonicals, hp);
            fi;
        od;
        if Length(s3_canonicals) = 0 then continue; fi;

        # Inner orbits: Stab_NH(L) acting on B.
        action := StabActionOnB(S, BL.hom_to_B, BL.pcgs, BL.d, 3);
        mats := action.mats;

        lift_act_B := function(W, n)
            local Mn, j, b, l, nl, exp;
            if BL.d = 0 then return W; fi;
            Mn := [];
            for j in [1..BL.d] do
                b := BL.pcgs[j];
                l := PreImagesRepresentative(BL.hom_to_B, b);
                nl := n^-1 * l * n;
                exp := ExponentsOfPcElement(BL.pcgs, Image(BL.hom_to_B, nl));
                Add(Mn, exp * One(GF(3)));
            od;
            if Length(W) = 0 then return W; fi;
            return OnSubspacesByCanonicalBasis(W, Mn);
        end;

        if Length(mats) = 0 then
            # S trivial — each S_3-hyperplane its own orbit, Stab = S.
            for W_rep in s3_canonicals do
                K_gens_in_L := [];
                for v in W_rep do
                    b_elem := Product(List([1..BL.d],
                        i -> BL.pcgs[i] ^ IntFFE(v[i])));
                    Add(K_gens_in_L,
                        PreImagesRepresentative(BL.hom_to_B, b_elem));
                od;
                K := SubgroupNC(H, Concatenation(NHL_gens, K_gens_in_L));
                Add(recs, rec(
                    K_H_gens := GeneratorsOfGroup(K),
                    Stab_NH_KH_gens := GeneratorsOfGroup(S),
                    # |Stab| = |S| since S acts trivially -- matches Stage A/B,
                    # lets the labelled harvest skip a fresh Schreier-Sims.
                    Stab_NH_KH_size := Size(S),
                    qid := qid,
                    qsize := qsize));
            od;
            continue;
        fi;

        Sgrp := Group(mats);
        # OrbitsDomain over s3_canonicals only is correct because S preserves
        # the filter (Stab_NH(L) maps S_3-kernels of H to S_3-kernels of H).
        orbits := OrbitsDomain(Sgrp, s3_canonicals, safe_act_subsp_b);

        for orb in orbits do
            W_rep := orb[1];
            K_gens_in_L := [];
            for v in W_rep do
                b_elem := Product(List([1..BL.d],
                    i -> BL.pcgs[i] ^ IntFFE(v[i])));
                Add(K_gens_in_L,
                    PreImagesRepresentative(BL.hom_to_B, b_elem));
            od;
            K := SubgroupNC(H, Concatenation(NHL_gens, K_gens_in_L));
            stab_S := Stabilizer(S, W_rep, lift_act_B);
            Add(recs, rec(
                K_H_gens := GeneratorsOfGroup(K),
                Stab_NH_KH_gens := GeneratorsOfGroup(stab_S),
                # |Stab_NH(K)| = |S| / |inner orbit|: L = preimage of [S_3,S_3]
                # = A_3 is characteristic in H/K, so Stab_NH(K) <= Stab_NH(L) = S
                # and within S it is the inner-subspace stabilizer.  Free from
                # the orbit; matches Stage A/B's Stab_NH_KH_size convention.
                Stab_NH_KH_size := Size(S) / Length(orb),
                qid := qid,
                qsize := qsize));
        od;
    od;
    return recs;
end;


# Rich variant: adds hom (H -> Q) and A_gens.  As with D_8, there is no clean
# two-layer factorization of H -> H/K, so fall back to
# NaturalHomomorphismByNormalSubgroup(H, K) and _StageB_InducedAutoGens.
LinearOrbitRecsS3Rich := function(H, N_H)
    local recs_plain, recs, r, K, hom, Q, stab_NH, A_gens;
    recs_plain := LinearOrbitRecsS3(H, N_H);
    recs := [];
    for r in recs_plain do
        K := SubgroupNC(H, r.K_H_gens);
        hom := NaturalHomomorphismByNormalSubgroup(H, K);
        Q := Range(hom);
        stab_NH := SubgroupNC(N_H, r.Stab_NH_KH_gens);
        A_gens := _StageB_InducedAutoGens(stab_NH, H, hom);
        Add(recs, rec(
            K_H_gens := r.K_H_gens,
            Stab_NH_KH_gens := r.Stab_NH_KH_gens,
            # Carry forward the plain variant's Stab_NH_KH_size (matches Stage B).
            Stab_NH_KH_size := r.Stab_NH_KH_size,
            qid := r.qid,
            qsize := r.qsize,
            hom := hom,
            Q := Q,
            A_gens := A_gens));
    od;
    return recs;
end;


# ---- Ground-truth oracles and comparators ----

# Generic slow oracle: kernels K ◁ H with H/K ≅ target group (by IdGroup),
# bucketed under N_H-conjugation.  Returns records with stabilizer gens.
_StageC_GroundTruthOrbits := function(H, N_H, qsize, target_id)
    local NS, kernels, orbits, K0, found, orb, K1;
    NS := NormalSubgroups(H);
    kernels := Filtered(NS, K ->
        Size(H) / Size(K) = qsize and IdGroup(FactorGroupNC(H, K)) = target_id);
    orbits := [];
    for K0 in kernels do
        found := false;
        for orb in orbits do
            for K1 in orb do
                if RepresentativeAction(N_H, K0, K1, OnPoints) <> fail then
                    Add(orb, K0);
                    found := true;
                    break;
                fi;
            od;
            if found then break; fi;
        od;
        if not found then Add(orbits, [K0]); fi;
    od;
    return List(orbits, function(orb)
        local rep, stab;
        rep := orb[1];
        stab := Stabilizer(N_H, rep, OnPoints);
        return rec(
            K_H_gens := GeneratorsOfGroup(rep),
            Stab_NH_KH_gens := GeneratorsOfGroup(stab),
            qid := [qsize, 0, target_id],
            qsize := qsize);
    end);
end;

GroundTruthS3Orbits := function(H, N_H)
    return _StageC_GroundTruthOrbits(H, N_H, 6, [6, 1]);
end;

GroundTruthC3Orbits := function(H, N_H)
    return _StageC_GroundTruthOrbits(H, N_H, 3, [3, 1]);
end;

# Generic parity check: compares orbit count + sorted stabilizer-order
# multiset of `linear` records against the ground-truth oracle.
_StageC_Compare := function(linear, truth)
    local sizes_l, sizes_t;
    sizes_l := SortedList(List(linear,
        r -> Size(Group(r.Stab_NH_KH_gens))));
    sizes_t := SortedList(List(truth,
        r -> Size(Group(r.Stab_NH_KH_gens))));
    return rec(
        ok := (Length(sizes_l) = Length(sizes_t)) and (sizes_l = sizes_t),
        n_linear := Length(linear),
        n_truth := Length(truth),
        stab_sizes_linear := sizes_l,
        stab_sizes_truth := sizes_t);
end;

CompareS3WithGroundTruth := function(H, N_H)
    return _StageC_Compare(LinearOrbitRecsS3(H, N_H), GroundTruthS3Orbits(H, N_H));
end;

CompareC3WithGroundTruth := function(H, N_H)
    return _StageC_Compare(LinearOrbitRecsCpa(H, N_H, 3, 1),
                           GroundTruthC3Orbits(H, N_H));
end;


Print("prototype_stage_c.g loaded.\n");
Print("  OrdinaryPFrattiniModuleData(H, L, p)\n");
Print("  LinearOrbitRecsS3(H, N_H)\n");
Print("  LinearOrbitRecsS3Rich(H, N_H)\n");
Print("  GroundTruthS3Orbits(H, N_H) / CompareS3WithGroundTruth(H, N_H)\n");
Print("  GroundTruthC3Orbits(H, N_H) / CompareC3WithGroundTruth(H, N_H)\n");
