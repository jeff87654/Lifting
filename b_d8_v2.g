################################################################################
# b_d8_v2.g
#
# Support-first enumeration of subdirect U <= F_2^{2k} mod S_k for [4,3]^k.
#
# Math: each U corresponds to an r x 2k generator matrix M with each block
# (= 2 columns) of rank 2 in F_2^r.  GL_r acts by row-ops (preserves U);
# S_k acts by column-pair permutation.  We want orbits under S_k only.
#
# Two-stage enumeration:
#   Stage 1 (W-multiset): GL_r x S_k orbits on multisets of 2-dim subspaces
#     W_i <= F_2^r spanning F_2^r.  Same as b_elemab(p=2, m=2, k, r).
#
#   Stage 2 (within-block refinement): for each W-multiset orbit rep
#     (S=(W_1..W_s), mult=(m_1..m_s), Stab <= GL_r x S_k), enumerate
#     orbits of ordered-basis assignments (config in (GL_2(F_2))^k) under
#     the natural Stab action.  Each orbit rep gives one b_d8 U-orbit.
#
# Output API matches existing BD8_EnumerateUorbits:
#   list of rec(U := subspace of F_2^{2k}, stab := list of S_k perms, dim := r)
################################################################################

if not IsBound(ELEMAB_GetGLrAsPermGroup) then
    Read("C:/Users/jeffr/Downloads/Lifting/b_elemab.g");
fi;

# Reference basis matrix B_W (r x 2 over F_2) for W given as nonzero-encoding set.
BD8V2_BasisFromEncodingSet := function(r, W_set)
    local vecs, V;
    vecs := List(W_set, e -> ELEMAB_VecDecode(2, r, e));
    V := Subspace(GF(2)^r, vecs);
    return TransposedMat(List(Basis(V), v -> ShallowCopy(v)));   # r x 2
end;

# Restrict g (perm on F_2^r \ 0 encodings) as iso W_src -> W_tgt: return 2x2.
# h such that g(B_src[:,j]) = sum_i h[i,j] * B_tgt[:,i]  (i.e. B_tgt * h col j).
BD8V2_GrToGL2 := function(g_perm, B_W_src, B_W_tgt, r)
    local src_cols, tgt_cols, gc1, gc2, sol1, sol2;
    src_cols := TransposedMat(B_W_src);
    tgt_cols := TransposedMat(B_W_tgt);
    gc1 := ELEMAB_VecDecode(2, r,
        ELEMAB_VecEncode(2, r, src_cols[1]) ^ g_perm);
    gc2 := ELEMAB_VecDecode(2, r,
        ELEMAB_VecEncode(2, r, src_cols[2]) ^ g_perm);
    sol1 := SolutionMat(tgt_cols, gc1);
    sol2 := SolutionMat(tgt_cols, gc2);
    if sol1 = fail or sol2 = fail then
        Error("BD8V2_GrToGL2: g(W_src) not contained in W_tgt");
    fi;
    return TransposedMat([sol1, sol2]);   # 2x2
end;

# Enumerate GL_2(F_2) as a list of 2x2 matrices, build index.
BD8V2_ENUM_GL2 := function()
    local F, all, M, a, b, c, d;
    F := GF(2);
    all := [];
    for a in [0,1] do for b in [0,1] do
    for c in [0,1] do for d in [0,1] do
        M := [[a, b], [c, d]] * One(F);
        if Determinant(M) <> Zero(F) then Add(all, M); fi;
    od; od; od; od;
    return all;
end;

BD8V2_GL2 := BD8V2_ENUM_GL2();
BD8V2_GL2_INDEX := function(M)
    local i;
    for i in [1..6] do
        if BD8V2_GL2[i] = M then return i; fi;
    od;
    Error("matrix not in GL_2(F_2): ", M);
end;

# Precomputed multiplication table: GL2_MULT[i][j] = index of GL_2[i] * GL_2[j].
BD8V2_GL2_MULT := List([1..6], i ->
    List([1..6], j -> BD8V2_GL2_INDEX(BD8V2_GL2[i] * BD8V2_GL2[j])));

# Build cfg permutation using precomputed GL_2 multiplication table.
# Action: new_c[sigma(i)] = h_i * c[i].
# h_per_pos[j] given as integers in [1..6] (= GL_2 indices), NOT matrices.
BD8V2_BuildCfgPerm := function(k, total_cfg, sigma_list, h_idx_per_pos)
    local perm_list, idx, x, ii, cfg_in, new_cfg, j, s, dest;
    perm_list := [];
    for idx in [1..total_cfg] do
        # decode idx -> cfg_in (k integers in [1..6])
        cfg_in := []; x := idx - 1;
        for ii in [1..k] do
            Add(cfg_in, (x mod 6) + 1);
            x := QuoInt(x, 6);
        od;
        # apply action
        new_cfg := List([1..k], i -> 0);
        for j in [1..k] do
            new_cfg[sigma_list[j]] :=
                BD8V2_GL2_MULT[h_idx_per_pos[j]][cfg_in[j]];
        od;
        # encode new_cfg -> dest
        s := 0;
        for ii in [k, k-1..1] do s := s * 6 + new_cfg[ii] - 1; od;
        Add(perm_list, s + 1);
    od;
    return PermList(perm_list);
end;

# Top-level enumeration.
BD8_EnumerateUorbitsV2 := function(setup)
    local k, F2, results, r, b_elemab_reps, rep, rec_data, all_subs,
          S, mults, support_size, type_of_pos, j, copy, B_W,
          A_grp, A_grp_gens, gen_g, total_cfg, action_gens,
          alpha, target_j, pos_block_start, pos_in_t, p,
          sigma_list, h_per_pos, t_j, perm_grp_on_cfg,
          cfg_orbits, orb_rep, orb_rep_cfg, M_built, blk, ipos, U_basis, U,
          stab_S_k, sigma, t_hb, n_processed, t_start, ix, x, ii, swap_sigma,
          cycle_sigma, total_orbs_at_r, vec_idx;
    k := setup.k;
    F2 := setup.F;
    results := [];
    t_start := Runtime();
    Print("[BD8V2] starting for k=", k, "\n");

    for r in [2..2*k] do
        Print("[BD8V2] rank r=", r, " (elapsed=", Runtime() - t_start, "ms)\n");
        b_elemab_reps := ELEMAB_EnumerateRankRReps(2, 2, k, r);
        Print("  [BD8V2] r=", r, " W-multiset orbits: ",
              Length(b_elemab_reps), "\n");
        n_processed := 0; t_hb := Runtime();
        total_orbs_at_r := 0;
        for rep in b_elemab_reps do
            n_processed := n_processed + 1;
            if Runtime() - t_hb > 30000 then
                Print("  [BD8V2] r=", r, " ", n_processed, "/",
                      Length(b_elemab_reps),
                      " elapsed=", Runtime() - t_start,
                      "ms |results|=", Length(results), "\n");
                t_hb := Runtime();
            fi;

            if IsBound(rep.full_T_k) and rep.full_T_k then
                # r = 2k single orbit; U = F_2^{2k}.
                U := setup.Q;
                stab_S_k := AsList(SymmetricGroup(k));
                Add(results, rec(U := U, stab := stab_S_k, dim := r));
                total_orbs_at_r := total_orbs_at_r + 1;
                continue;
            fi;

            S := rep.S;
            mults := rep.mults;
            support_size := Length(S);
            rec_data := ELEMAB_GLrOnSubspaces(2, r, 2);
            all_subs := rec_data.all_subs;

            B_W := List([1..support_size], j ->
                BD8V2_BasisFromEncodingSet(r, all_subs[S[j]]));

            type_of_pos := [];
            for j in [1..support_size] do
                for copy in [1..mults[j]] do
                    Add(type_of_pos, j);
                od;
            od;

            # Position-block starts.
            pos_block_start := [];
            pos_in_t := 1;
            for j in [1..support_size] do
                Add(pos_block_start, pos_in_t);
                pos_in_t := pos_in_t + mults[j];
            od;

            total_cfg := 6^k;
            action_gens := [];
            action_sigmas := [];     # parallel: S_k-projection of each gen

            # Stab(S, mults) in GL_r-perm-group: first restrict to Stab(Set(S)) (fast,
            # standard OnSets action), then to mult-preserving subset (small group, fast).
            sigma := ELEMAB_GetGLrAsPermGroup(2, r);
            t_j := GeneratorsOfGroup(sigma);
            ix := List(t_j, g -> PermList(List([1..rec_data.n_subs], i ->
                PositionSorted(rec_data.all_subs,
                    ELEMAB_OnSubspaceSet(rec_data.all_subs[i], g)))));
            x := GroupHomomorphismByImagesNC(sigma,
                rec_data.group_on_indices, t_j, ix);
            # Stab(Set(S), OnSets) in group_on_indices: fast standard action.
            ii := Stabilizer(rec_data.group_on_indices, Set(S), OnSets);
            # Refine to Stab(S, mults) within ii (now a small group).
            ii := Stabilizer(ii,
                Set(List([1..support_size], j -> [S[j], mults[j]])),
                function(tagged, g)
                    return Set(List(tagged, pp -> [pp[1] ^ g, pp[2]]));
                end);
            A_grp := PreImage(x, ii);
            A_grp_gens := SmallGeneratingSet(A_grp);

            for gen_g in A_grp_gens do
                vec_idx := Image(x, gen_g);
                alpha := [];
                for j in [1..support_size] do
                    target_j := Position(S, S[j] ^ vec_idx);
                    Add(alpha, target_j);
                od;
                sigma_list := [];
                for j in [1..support_size] do
                    for p in [1..mults[j]] do
                        Add(sigma_list, pos_block_start[alpha[j]] + p - 1);
                    od;
                od;
                h_per_pos := [];
                for j in [1..k] do
                    t_j := type_of_pos[j];
                    Add(h_per_pos, BD8V2_GL2_INDEX(BD8V2_GrToGL2(gen_g,
                        B_W[t_j], B_W[alpha[t_j]], r)));
                od;
                Add(action_gens,
                    BD8V2_BuildCfgPerm(k, total_cfg, sigma_list, h_per_pos));
                Add(action_sigmas, PermList(sigma_list));
            od;

            # Intra-type S_{m_j} symmetry generators.  h_per_pos = identity GL_2 = index 1
            # (the identity matrix in the BD8V2_GL2 list is always at index 1).
            for j in [1..support_size] do
                if mults[j] >= 2 then
                    h_per_pos := List([1..k], i ->
                        BD8V2_GL2_INDEX(One(BD8V2_GL2[1])));
                    swap_sigma := List([1..k], i -> i);
                    swap_sigma[pos_block_start[j]] := pos_block_start[j] + 1;
                    swap_sigma[pos_block_start[j] + 1] := pos_block_start[j];
                    Add(action_gens,
                        BD8V2_BuildCfgPerm(k, total_cfg, swap_sigma, h_per_pos));
                    Add(action_sigmas, PermList(swap_sigma));
                    if mults[j] >= 3 then
                        cycle_sigma := List([1..k], i -> i);
                        for p in [1..mults[j] - 1] do
                            cycle_sigma[pos_block_start[j] + p - 1] :=
                                pos_block_start[j] + p;
                        od;
                        cycle_sigma[pos_block_start[j] + mults[j] - 1] :=
                            pos_block_start[j];
                        Add(action_gens,
                            BD8V2_BuildCfgPerm(k, total_cfg, cycle_sigma, h_per_pos));
                        Add(action_sigmas, PermList(cycle_sigma));
                    fi;
                fi;
            od;

            # Build perm group on cfg and S_k-projection hom.
            if Length(action_gens) = 0 then
                cfg_orbits := List([1..total_cfg], i -> [i]);
                perm_grp_on_cfg := fail;
                cycle_sigma := fail;   # holds projection hom (or fail)
            else
                perm_grp_on_cfg := Group(action_gens);
                cfg_orbits := OrbitsDomain(perm_grp_on_cfg, [1..total_cfg]);
                cycle_sigma := GroupHomomorphismByImagesNC(
                    perm_grp_on_cfg, Group(action_sigmas, ()),
                    action_gens, action_sigmas);
            fi;

            for orb_rep in cfg_orbits do
                # decode orb_rep[1] -> cfg list
                orb_rep_cfg := [];
                x := orb_rep[1] - 1;
                for ii in [1..k] do
                    Add(orb_rep_cfg, (x mod 6) + 1);
                    x := QuoInt(x, 6);
                od;
                M_built := List([1..r], i -> []);
                for ipos in [1..k] do
                    blk := B_W[type_of_pos[ipos]] *
                           BD8V2_GL2[orb_rep_cfg[ipos]];
                    for j in [1..r] do
                        Append(M_built[j], blk[j]);
                    od;
                od;
                U_basis := M_built * One(F2);
                U := Subspace(setup.Q, U_basis);
                # Stab_{S_k}(U) = image of Stabilizer(cfg-perm-group, orb_rep[1]).
                if perm_grp_on_cfg = fail then
                    stab_S_k := [()];
                else
                    swap_sigma := Stabilizer(perm_grp_on_cfg, orb_rep[1]);
                    stab_S_k := AsList(Image(cycle_sigma, swap_sigma));
                fi;
                Add(results, rec(U := U, stab := stab_S_k, dim := r));
                total_orbs_at_r := total_orbs_at_r + 1;
            od;
        od;
        Print("  [BD8V2] r=", r, " orbits added: ", total_orbs_at_r,
              " (total so far: ", Length(results), ")\n");
    od;
    Print("[BD8V2] complete: ", Length(results), " orbits in ",
          Runtime() - t_start, "ms\n");
    return results;
end;
