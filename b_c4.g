################################################################################
# b_c4.g
#
# Frattini-factor enumeration of FPF subgroup conjugacy classes for C_4^k
# (= [4,1]^k in transitive-group notation).
#
# Math:
#   G = C_4^k (abelian), Phi(G) = G^2 = (C_2)^k = Z = F_2^k.
#   Q = G/Phi = (C_2)^k = F_2^k (NOT F_2^{2k} as in D_8).
#   q: Q -> Z is LINEAR: q(u) = u  (since 2*r_i = z_i and lift via r_i^{u_i}
#     gives 2*section(u) = sum u_i * z_i = u).
#   B = 0 (abelian).
#
#   Ambient = N_{S_{4k}}(C_4^k) = N_{S_4}(C_4) wr S_k = D_8 wr S_k.
#   Action: S_k permutes blocks; within each block, C_2 inversion (r -> r^{-1}).
#   Within-block C_2 acts trivially on Q and Z (both are F_2),
#   but non-trivially on ell: at block i, ell(b) -> ell(b) + b[i]*e_i mod C.
#
#   Each subgroup H <= G corresponds to a triple (U, C, ell) where:
#     U = HPhi/Phi <= Q, subdirect (each block projection nonzero)
#     C = H ∩ Phi <= Z, with U <= C  (= q(U) <= C constraint).
#     ell ∈ Hom(U, Z/C) mod (per-block C_2 inversion + Stab(U,C) ⊂ S_k).
################################################################################

if not IsBound(ELEMAB_GetGLrAsPermGroup) then
    Read("C:/Users/jeffr/Downloads/Lifting/b_elemab.g");
fi;

# Setup record.
BC4_Setup := function(k)
    local F, Q, Z, e_Q, e_Z;
    F := GF(2);
    Q := F^k;
    Z := F^k;
    e_Q := Basis(Q);
    e_Z := Basis(Z);
    return rec(F := F, k := k, Q := Q, Z := Z,
               e_Q := e_Q, e_Z := e_Z);
end;

# S_k action on Q = F_2^k: permute coordinates.
BC4_PermQ := function(setup, sigma, u)
    local v, i;
    v := ListWithIdenticalEntries(setup.k, Zero(setup.F));
    for i in [1..setup.k] do
        v[i^sigma] := u[i];
    od;
    return v * One(setup.F);
end;
BC4_PermZ := BC4_PermQ;     # same shape

BC4_PermSubspaceQ := function(setup, sigma, U)
    return Subspace(setup.Q,
        List(Basis(U), v -> BC4_PermQ(setup, sigma, v)));
end;
BC4_PermSubspaceZ := function(setup, sigma, C)
    return Subspace(setup.Z,
        List(Basis(C), v -> BC4_PermQ(setup, sigma, v)));
end;

# 2-cocycle f: Q x Q -> Z from the C_4 lift formula.
#   lift_U(u) * lift_U(v) = lift_U(u+v) * lift_Z(f(u,v))
# At block i: r_i^{u_i} * r_i^{v_i} = r_i^{u_i + v_i (integer)}; if u_i = v_i = 1
# this is r_i^2 = z_i, while lift_U((u+v) mod 2) = r_i^0 = e.  So f(u,v)_i =
# u_i * v_i (Hadamard product, symmetric since C_4 is abelian).
BC4_F := function(setup, u, v)
    local i, result;
    result := List([1..setup.k], i -> Zero(setup.F));
    for i in [1..setup.k] do
        result[i] := u[i] * v[i];
    od;
    return result * One(setup.F);
end;

# Subdirect = each block (= coordinate) has rank 1 in U
# = each column of U-basis-matrix has a 1 somewhere
# = projection π_i(U) = F_2 for each i
# = i-th coordinate is not identically 0 on U.
BC4_IsSubdirect := function(setup, U)
    local i, U_basis, found;
    U_basis := AsList(Basis(U));
    if Length(U_basis) = 0 then return setup.k = 0; fi;
    for i in [1..setup.k] do
        if not ForAny(U_basis, v -> v[i] = One(setup.F)) then
            return false;
        fi;
    od;
    return true;
end;

# ---- enumerate subdirect U orbits mod S_k via b_elemab ----------------------
# b_elemab(p=2, m=1, k, r) gives orbits of size-k multisets of nonzero F_2^r
# vectors under GL_r x S_k.  Note: for b_c4 the within-block "GL_1 = trivial"
# is absorbed (no extra refinement needed since 1-dim within-block has trivial
# Aut).  So b_elemab orbits directly give b_c4 U-orbits mod S_k.
BC4_EnumerateUorbits := function(setup)
    local k, F, Q, results, r, b_elemab_reps, rep, rec_data, all_subs,
          S, mults, support_size, type_of_pos, j, copy, B_W, ipos,
          U_basis, U, stab_S_k, sigma_test, A_grp, A_grp_idx, A_grp_gens,
          glr_perm, t_j, ix, x, gen_g, sigma, alpha, target_j, vec_idx,
          sigma_list, pos_block_start, pos_in_t, p, sigma_full;
    k := setup.k;
    F := setup.F;
    Q := setup.Q;
    results := [];
    Print("[BC4_U] starting for k=", k, "\n");
    for r in [1..k] do
        b_elemab_reps := ELEMAB_EnumerateRankRReps(2, 1, k, r);
        if Length(b_elemab_reps) = 0 then continue; fi;
        for rep in b_elemab_reps do
            if IsBound(rep.full_T_k) and rep.full_T_k then
                # r = k, single orbit: U = F_2^k.
                U := Q;
                stab_S_k := AsList(SymmetricGroup(k));
                Add(results, rec(U := U, stab := stab_S_k, dim := r));
                continue;
            fi;
            S := rep.S;
            mults := rep.mults;
            support_size := Length(S);
            rec_data := ELEMAB_GLrOnSubspaces(2, r, 1);   # m=1 subspaces of F_2^r
            all_subs := rec_data.all_subs;

            # For each support element, the corresponding "column vector" in F_2^r.
            # The 1-dim subspace W_j has exactly 1 nonzero element: take it as col.
            B_W := [];  # k columns, but we encode as r-vector list
            for j in [1..support_size] do
                Add(B_W, ELEMAB_VecDecode(2, r,
                    AsList(all_subs[S[j]])[1]));
            od;

            # type_of_pos[i] = support index for position i.
            type_of_pos := [];
            for j in [1..support_size] do
                for copy in [1..mults[j]] do
                    Add(type_of_pos, j);
                od;
            od;
            # Build U-basis as r x k matrix: column i = B_W[type_of_pos[i]].
            # As row list (r vectors of length k), row p = (B_W[type_of_pos[i]][p] for i in 1..k).
            U_basis := List([1..r], p ->
                List([1..k], i -> B_W[type_of_pos[i]][p]));
            U_basis := U_basis * One(F);
            U := Subspace(Q, U_basis);

            # Stab_{S_k}(U) = subgroup of S_k preserving the W-multiset (combined alpha + intra-type).
            # Since within-block "GL_1" is trivial, this is just the S_k action.
            # Compute via Stab(tagged multiset) in group_on_indices, project to S_k.
            glr_perm := ELEMAB_GetGLrAsPermGroup(2, r);
            t_j := GeneratorsOfGroup(glr_perm);
            ix := List(t_j, g -> PermList(List([1..rec_data.n_subs], i ->
                PositionSorted(rec_data.all_subs,
                    ELEMAB_OnSubspaceSet(rec_data.all_subs[i], g)))));
            x := GroupHomomorphismByImagesNC(glr_perm,
                rec_data.group_on_indices, t_j, ix);
            A_grp_idx := Stabilizer(rec_data.group_on_indices, Set(S), OnSets);
            A_grp_idx := Stabilizer(A_grp_idx,
                Set(List([1..support_size], j -> [S[j], mults[j]])),
                function(tagged, g)
                    return Set(List(tagged, pp -> [pp[1] ^ g, pp[2]]));
                end);
            A_grp := PreImage(x, A_grp_idx);
            A_grp_gens := SmallGeneratingSet(A_grp);

            # Build position-block starts.
            pos_block_start := [];
            pos_in_t := 1;
            for j in [1..support_size] do
                Add(pos_block_start, pos_in_t);
                pos_in_t := pos_in_t + mults[j];
            od;

            # Project to S_k: for each gen of A_grp, get sigma_list.
            stab_S_k := [()];
            sigma := Group([()]);   # placeholder
            sigma_full := [];
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
                Add(sigma_full, PermList(sigma_list));
            od;
            # Plus intra-type S_{m_j} generators.
            for j in [1..support_size] do
                if mults[j] >= 2 then
                    sigma_list := List([1..k], i -> i);
                    sigma_list[pos_block_start[j]] := pos_block_start[j] + 1;
                    sigma_list[pos_block_start[j] + 1] := pos_block_start[j];
                    Add(sigma_full, PermList(sigma_list));
                    if mults[j] >= 3 then
                        sigma_list := List([1..k], i -> i);
                        for p in [1..mults[j] - 1] do
                            sigma_list[pos_block_start[j] + p - 1] :=
                                pos_block_start[j] + p;
                        od;
                        sigma_list[pos_block_start[j] + mults[j] - 1] :=
                            pos_block_start[j];
                        Add(sigma_full, PermList(sigma_list));
                    fi;
                fi;
            od;
            # sigma_full may contain ().  Build group; trivial group if all ().
            sigma_full := Filtered(sigma_full, p -> p <> ());
            if Length(sigma_full) = 0 then
                stab_S_k := [()];
            else
                stab_S_k := AsList(Group(sigma_full));
            fi;
            Add(results, rec(U := U, stab := stab_S_k, dim := r));
        od;
    od;
    Print("[BC4_U] complete: ", Length(results), " U-orbits\n");
    return results;
end;

# ---- enumerate C orbits mod Stab(U) -----------------------------------------
# C <= Z = F_2^k with C ⊇ U (= q(U) constraint).  Mod Stab(U).
BC4_EnumerateCorbits := function(setup, U_rec)
    local U, Cmin, C, results, seen_keys, canon, sigma, image, key,
          perm_stab, pos;
    U := U_rec.U;
    Cmin := U;    # q(U) = U; constraint C >= U.
    seen_keys := [];
    results := [];
    for C in Subspaces(setup.Z) do
        if not IsSubset(C, Cmin) then continue; fi;
        canon := fail;
        for sigma in U_rec.stab do
            image := BC4_PermSubspaceZ(setup, sigma, C);
            key := SortedList(AsList(image));
            if canon = fail or key < canon then canon := key; fi;
        od;
        pos := PositionSorted(seen_keys, canon);
        if pos > Length(seen_keys) or seen_keys[pos] <> canon then
            Add(seen_keys, canon, pos);
            perm_stab := Filtered(U_rec.stab,
                sigma -> BC4_PermSubspaceZ(setup, sigma, C) = C);
            Add(results, rec(C := C, stab := perm_stab,
                              C_dim := Dimension(C)), pos);
        fi;
    od;
    return results;
end;

# ---- enumerate ell orbits mod (Stab(U,C) + per-block C_2 inversion) ---------
# ell ∈ Hom(U, Z/C).  R is generated by:
#   - per-block C_2 inversion at block i: ell(b) -> ell(b) + b[i] * e_i.
# Encode ell as flat F_2-vector of length L_dim = (dim U) * (dim Z/C).
BC4_LiftOrbitReps := function(setup, U_rec, C_rec)
    local U, C, U_dim, C_dim, ZC_dim, L_dim, basis_U, hom_ZC, basis_ZC,
          basis_ZC_lifts, R_basis, ell_w, i, L, R, E_size, sigma, sigma_inv,
          M, N, action, e_canon, e_reps_keys, e_reps, idx, j, v,
          perm_list, sig_perm, orbits, L_list, r_red, orbit_reps,
          inversion_vec, e_i_in_Z, e_i_image,
          delta_flat, supp_ii, z_correction, run_v;
    U := U_rec.U;
    C := C_rec.C;
    U_dim := Dimension(U);
    C_dim := Dimension(C);
    ZC_dim := Dimension(setup.Z) - C_dim;
    L_dim := U_dim * ZC_dim;
    if L_dim = 0 then
        return rec(count := 1, reps := [[]]);
    fi;

    basis_U := AsList(Basis(U));
    hom_ZC := NaturalHomomorphismBySubspace(setup.Z, C);
    basis_ZC := AsList(Basis(Range(hom_ZC)));
    basis_ZC_lifts := List(basis_ZC,
        b -> PreImagesRepresentative(hom_ZC, b));

    L := setup.F^L_dim;
    # Build R: per-block C_2 inversion contributions.
    # Inversion at block i: ell(b_j) -> ell(b_j) + b_j[i] * e_i mod C.
    # As flat ell vector: ell-flat = concat over j of ell(b_j) entries.
    # Each ell(b_j) is encoded as ZC_dim entries (= ell(b_j) in basis_ZC).
    # Inversion at block i: adds b_j[i] * (image of e_i in Z/C) to ell(b_j)[*].
    R_basis := [];
    for i in [1..setup.k] do
        e_i_in_Z := ListWithIdenticalEntries(setup.k, Zero(setup.F));
        e_i_in_Z[i] := One(setup.F);
        e_i_in_Z := e_i_in_Z * One(setup.F);
        e_i_image := AsList(Image(hom_ZC, e_i_in_Z));
        # If e_i ∈ C, e_i_image = 0; skip.
        if ForAll(e_i_image, x -> IsZero(x)) then continue; fi;
        # Flat vector: for each basis b_j of U, contribution = b_j[i] * e_i_image.
        inversion_vec := Concatenation(List(basis_U,
            b_j -> b_j[i] * e_i_image));
        Add(R_basis, inversion_vec);
    od;
    if Length(R_basis) = 0 then
        R := Subspace(L, [Zero(L)]);
    else
        R := Subspace(L, R_basis);
    fi;
    E_size := Size(L) / Size(R);
    if Size(R) = 1 then
        r_red := [];
    else
        r_red := SemiEchelonBasis(R);
    fi;
    e_canon := function(v_in)
        if Length(r_red) = 0 then return v_in; fi;
        return SiftedVector(r_red, v_in);
    end;
    L_list := AsList(L);
    e_reps_keys := [];
    e_reps := [];
    for j in [1..Length(L_list)] do
        v := e_canon(L_list[j]);
        idx := PositionSorted(e_reps_keys, v);
        if idx > Length(e_reps_keys) or e_reps_keys[idx] <> v then
            Add(e_reps_keys, v, idx);
            Add(e_reps, v, idx);
        fi;
    od;
    if Length(C_rec.stab) <= 1 then
        return rec(count := E_size, reps := e_reps);
    fi;

    # Sigma-permutation of e_reps under S_k stab.
    # The action of sigma on ell in Hom(U, Z/C) is AFFINE: when
    # sigma^-1(b_i) = sum_k M[i][k] b_k expands as a multi-term sum, the
    # cocycle relation ell(b_{j1}+...+b_{jn}) = sum_k ell(b_{jk}) +
    # sum_{k=2..n} f(s_{k-1}, b_{jk}) introduces a per-sigma constant shift
    # delta.  (Same bug as the original D8 action; see BD8_LiftOrbitReps.)
    perm_list := [];
    for sigma in C_rec.stab do
        sigma_inv := Inverse(sigma);
        # M = sigma-action on U-basis (as basis change matrix).
        M := List(basis_U, u_i -> SolutionMat(basis_U,
            BC4_PermQ(setup, sigma_inv, u_i))) * One(setup.F);
        N := List(basis_ZC_lifts,
            b -> AsList(Image(hom_ZC, BC4_PermZ(setup, sigma, b))))
            * One(setup.F);
        # Build the affine shift delta_sigma in L from the f-cocycle.
        delta_flat := [];
        for i in [1..U_dim] do
            supp_ii := Filtered([1..U_dim],
                jj -> M[i][jj] = One(setup.F));
            z_correction := Zero(setup.Z);
            if Length(supp_ii) >= 2 then
                run_v := ShallowCopy(basis_U[supp_ii[1]]);
                for j in [2..Length(supp_ii)] do
                    z_correction := z_correction +
                        BC4_F(setup, run_v, basis_U[supp_ii[j]]);
                    run_v := run_v + basis_U[supp_ii[j]];
                od;
            fi;
            Append(delta_flat,
                AsList(Image(hom_ZC,
                    BC4_PermZ(setup, sigma, z_correction))) * One(setup.F));
        od;
        action := function(v_in)
            local result, ii, jj, chunk, tj;
            result := [];
            for ii in [1..U_dim] do
                chunk := ListWithIdenticalEntries(ZC_dim, Zero(setup.F));
                for jj in [1..U_dim] do
                    if M[ii][jj] = One(setup.F) then
                        tj := v_in{[(jj-1)*ZC_dim+1 .. jj*ZC_dim]} * N;
                        chunk := chunk + tj;
                    fi;
                od;
                Append(result, chunk);
            od;
            return e_canon((result + delta_flat) * One(setup.F));
        end;
        sig_perm := PermList(List(e_reps,
            r -> PositionSorted(e_reps_keys, action(r))));
        Add(perm_list, sig_perm);
    od;
    orbits := Orbits(Group(perm_list, ()), [1..Length(e_reps)]);
    orbit_reps := List(orbits, o -> e_reps[o[1]]);
    return rec(count := Length(orbits), reps := orbit_reps);
end;

BC4_CountLiftOrbits := function(setup, U_rec, C_rec)
    return BC4_LiftOrbitReps(setup, U_rec, C_rec).count;
end;

# ---- materializer ------------------------------------------------------------
BC4_BlockData := function(k)
    local T, elts, r_T, blocks, i, shift;
    T := TransitiveGroup(4, 1);   # C_4
    elts := AsList(T);
    r_T := First(elts, x -> Order(x) = 4);
    if r_T = fail then Error("could not find r_T in C_4"); fi;
    blocks := [];
    for i in [1..k] do
        shift := MappingPermListList([1..4], [4*(i-1)+1 .. 4*i]);
        Add(blocks, rec(r := r_T ^ shift,
                        z := (r_T^2) ^ shift));
    od;
    return blocks;
end;

# u in F_2^k: block i bit u_i = 1 means use r_i.
BC4_LiftU := function(setup, blocks, u)
    local result, i;
    result := ();
    for i in [1..setup.k] do
        if u[i] = One(setup.F) then result := result * blocks[i].r; fi;
    od;
    return result;
end;

BC4_LiftZ := function(setup, blocks, z)
    local result, i;
    result := ();
    for i in [1..setup.k] do
        if z[i] = One(setup.F) then result := result * blocks[i].z; fi;
    od;
    return result;
end;

BC4_MaterializeTriple := function(setup, blocks, U_rec, C_rec, ell_flat)
    local basis_U, basis_C, hom_ZC, basis_ZC, basis_ZC_lifts, ZC_dim, n,
          gens, j, ell_j_vec, ell_j_lift, i, h_j, c;
    basis_U := AsList(Basis(U_rec.U));
    basis_C := AsList(Basis(C_rec.C));
    hom_ZC := NaturalHomomorphismBySubspace(setup.Z, C_rec.C);
    basis_ZC := AsList(Basis(Range(hom_ZC)));
    basis_ZC_lifts := List(basis_ZC,
        b -> PreImagesRepresentative(hom_ZC, b));
    n := Length(basis_U);
    ZC_dim := Length(basis_ZC);
    gens := [];
    for j in [1..n] do
        ell_j_vec := ell_flat{[(j-1)*ZC_dim+1 .. j*ZC_dim]};
        ell_j_lift := Zero(setup.Z);
        for i in [1..ZC_dim] do
            if ell_j_vec[i] = One(setup.F) then
                ell_j_lift := ell_j_lift + basis_ZC_lifts[i];
            fi;
        od;
        h_j := BC4_LiftU(setup, blocks, basis_U[j]) *
               BC4_LiftZ(setup, blocks, ell_j_lift);
        Add(gens, h_j);
    od;
    for c in basis_C do
        Add(gens, BC4_LiftZ(setup, blocks, c));
    od;
    return gens;
end;

BC4_FormatGenList := function(gens)
    return Concatenation("[",
        JoinStringsWithSeparator(List(gens, g -> String(g)), ","),
        "]");
end;

WriteBC4File := function(k, output_path)
    local setup, blocks, U_orbits, U_rec, C_orbits, C_rec, t0, fout,
          total, all_triples, lift_res, ell_rep, gens, u_idx, t_hb,
          combo_pairs, write_idx, bc4_cs_sum, bc4_fact;
    setup := BC4_Setup(k);
    blocks := BC4_BlockData(k);
    t0 := Runtime();
    Print("[BC4w] k=", k, " starting (output ", output_path, ")\n");
    U_orbits := BC4_EnumerateUorbits(setup);
    Print("[BC4w] U orbits: ", Length(U_orbits),
          " (enum_ms=", Runtime() - t0, ")\n");
    all_triples := [];
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BC4_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            lift_res := BC4_LiftOrbitReps(setup, U_rec, C_rec);
            for ell_rep in lift_res.reps do
                Add(all_triples, [U_rec, C_rec, ell_rep]);
            od;
        od;
        if Runtime() - t_hb >= 30000 or u_idx = Length(U_orbits) then
            Print("[BC4w] u=", u_idx, "/", Length(U_orbits),
                  " triples=", Length(all_triples),
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    total := Length(all_triples);
    Print("[BC4w] total reps: ", total,
          " (enum+orbit_ms=", Runtime() - t0, ")\n");

    # HARVEST: same UC telescoping as BD8.  Per (U,C):
    #   sum_l cs = (4k)! * 2^L_dim / (8^k * |C_rec.stab|),  L_dim=U_dim*(k-C_dim)
    bc4_cs_sum := 0;
    bc4_fact := Factorial(4 * k);
    for U_rec in U_orbits do
        for C_rec in BC4_EnumerateCorbits(setup, U_rec) do
            bc4_cs_sum := bc4_cs_sum + bc4_fact *
                2^(Dimension(U_rec.U) * (setup.k - Dimension(C_rec.C))) /
                (8^setup.k * Length(C_rec.stab));
        od;
    od;
    fout := OutputTextFile(output_path, false);
    SetPrintFormattingStatus(fout, false);
    combo_pairs := List([1..k], i -> [4, 1]);
    PrintTo(fout, "# combo: ", combo_pairs, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", Runtime() - t0, "\n");
    PrintTo(fout, "# class_sum: ", bc4_cs_sum, "\n");
    t_hb := Runtime();
    for write_idx in [1..total] do
        gens := BC4_MaterializeTriple(setup, blocks,
            all_triples[write_idx][1], all_triples[write_idx][2],
            all_triples[write_idx][3]);
        PrintTo(fout, BC4_FormatGenList(gens), "\n");
        if Runtime() - t_hb >= 30000 or write_idx = total then
            Print("[BC4w] materialized ", write_idx, "/", total,
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    CloseStream(fout);
    Print("[BC4w] Wrote ", output_path, "\n");
    return total;
end;

BC4_CountAll := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, total, contrib, u_idx, t0;
    setup := BC4_Setup(k);
    t0 := Runtime();
    U_orbits := BC4_EnumerateUorbits(setup);
    total := 0;
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BC4_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            total := total + BC4_CountLiftOrbits(setup, U_rec, C_rec);
        od;
    od;
    Print("[BC4] k=", k, " total=", total, " (", Runtime() - t0, "ms)\n");
    return total;
end;
