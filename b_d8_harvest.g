###############################################################################
# b_d8_harvest.g
#
# Engine harvest of class sizes for D_8^k FPF combos ([4,3]^k partitions).
# Implements the validated formula
#     cs(H) = (4k)! / ( |N_{D_8^k}(H)| * |Stab_{S_k}(triple-of-H)| )
# obtained ENTIRELY from engine data (no Normalizer call):
#   * |Stab_{S_k}(triple)| = |C_rec.stab| / (ell-orbit length under C_rec.stab)
#   * |N_{D_8^k}(H)| = 8^k / 2^{dim R(U,C)}    [closed form]
#       where R is the coboundary subspace the engine already builds.
#       Derivation: G=D_8^k, Q=G/Z=F_2^{2k}.  Inner conjugation by b in G shifts
#       section ell by ell_b(u)=B(b,u) mod C; image = R, kernel in Q has
#       dim 2k - dim R.  Z is central -> Z <= N_G(H).  So |N_G(H)| = |Z|*|ker|
#       = 2^k * 2^{2k - dim R} = 8^k / 2^{dim R}.
#
# Validated against the post-pass oracle for k=1,2,3 (cs sums 3, 7560, 271933200).
# Per-rep cost: zero arithmetic.
###############################################################################

Read("C:/Users/jeffr/Downloads/Lifting/b_d8.g");

# Modified LiftOrbitReps that also returns the orbit-length per rep.
# (Mirrors BD8_LiftOrbitReps; differs only in returning orbit_lens.)
BD8_LiftOrbitRepsH := function(setup, U_rec, C_rec)
    local U, C, U_dim, C_dim, ZC_dim, L_dim, basis_U, hom_ZC, basis_ZC,
          basis_ZC_lifts, R_basis, w, ell_w, L, R, E_size, sigma, sigma_inv,
          M, N, action, e_canon, e_reps_keys, e_reps, i, j, v,
          perm_list, sig_perm, orbits, hom_LR,
          delta_flat, perm_list2, z_correction, orbit_lens, o, orbit_reps;
    U := U_rec.U;
    C := C_rec.C;
    U_dim := Dimension(U);
    C_dim := Dimension(C);
    ZC_dim := Dimension(setup.Z) - C_dim;
    L_dim := U_dim * ZC_dim;
    if L_dim = 0 then
        # L trivial -> R trivial -> dim_R = 0 -> |N_G(H)| = 8^k
        return rec(count := 1, reps := [[]], orbit_lens := [1], dim_R := 0);
    fi;
    basis_U := AsList(Basis(U));
    hom_ZC := NaturalHomomorphismBySubspace(setup.Z, C);
    basis_ZC := AsList(Basis(Range(hom_ZC)));
    basis_ZC_lifts := List(basis_ZC,
        b -> PreImagesRepresentative(hom_ZC, b));
    L := setup.F ^ L_dim;
    R_basis := [];
    for w in Basis(setup.Q) do
        ell_w := Concatenation(List(basis_U, u ->
            AsList(Image(hom_ZC, BD8_B(setup, w, u)))));
        Add(R_basis, ell_w * One(setup.F));
    od;
    R := Subspace(L, R_basis);
    E_size := Size(L) / Size(R);
    e_canon := function(v_in) return SiftedVector(SemiEchelonBasis(R), v_in); end;
    if Size(R) = 1 then
        e_reps := AsList(L);
    elif Size(R) = Size(L) then
        e_reps := [Zero(L)];
    else
        hom_LR := NaturalHomomorphismBySubspace(L, R);
        e_reps := List(AsList(Range(hom_LR)),
                       q -> e_canon(PreImagesRepresentative(hom_LR, q)));
    fi;
    e_reps_keys := ShallowCopy(e_reps);
    SortParallel(e_reps_keys, e_reps);
    if Length(C_rec.stab) <= 1 then
        # trivial stab: every ell is its own orbit
        return rec(count := E_size, reps := e_reps,
                   orbit_lens := ListWithIdenticalEntries(E_size, 1),
                   dim_R := Dimension(R));
    fi;
    perm_list := [];
    for sigma in C_rec.stab do
        sigma_inv := Inverse(sigma);
        M := List(basis_U, u_i -> SolutionMat(basis_U,
            BD8_PermQ(setup, sigma_inv, u_i))) * One(setup.F);
        N := List(basis_ZC_lifts,
            b -> AsList(Image(hom_ZC, BD8_PermZ(setup, sigma, b))))
            * One(setup.F);
        delta_flat := [];
        for i in [1..U_dim] do
            perm_list2 := Filtered([1..U_dim],
                jj -> M[i][jj] = One(setup.F));
            z_correction := Zero(setup.Z);
            if Length(perm_list2) >= 2 then
                v := ShallowCopy(basis_U[perm_list2[1]]);
                for j in [2..Length(perm_list2)] do
                    z_correction := z_correction +
                        BD8_F(setup, v, basis_U[perm_list2[j]]);
                    v := v + basis_U[perm_list2[j]];
                od;
            fi;
            Append(delta_flat,
                AsList(Image(hom_ZC,
                    BD8_PermZ(setup, sigma, z_correction))) * One(setup.F));
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
    orbit_lens := List(orbits, Length);
    return rec(count := Length(orbits), reps := orbit_reps,
               orbit_lens := orbit_lens, dim_R := Dimension(R));
end;

# BD8_BaseGroup: the small ambient G = D_8^k as a permutation subgroup of S_{4k}.
# (Retained for sanity checks; no longer used by the closed-form harvest.)
BD8_BaseGroup := function(blocks)
    local gens, b;
    gens := [];
    for b in blocks do
        Add(gens, b.r);
        Add(gens, b.s);
    od;
    return Group(gens);
end;

# BD8_ClassSumUC(k)
#   Ultra-fast class_sum: skips ell-orbit enumeration entirely.  Derivation:
#     class_sum = sum over (U,C,ell-orbit) of cs
#               = sum over (U,C) of [ sum over ell-orbits of fact_n*orbit_len
#                                     / (NG_size * |C_rec.stab|) ]
#               = sum over (U,C) of fact_n * E_size / (NG_size * |C_rec.stab|)
#     E_size = 2^{L_dim - dim R},  NG_size = 8^k / 2^{dim R}, so dim R cancels:
#     per (U,C) contribution = fact_n * 2^{L_dim} / (8^k * |C_rec.stab|)
#   Cost: just U-orbit + per-U C-orbit enumeration -- the engine's natural
#   counting work; no ell-orbit perm-action computation needed.
BD8_ClassSumUC := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, t0, t_hb, u_idx,
          U_dim, C_dim, L_dim, contrib, class_sum, fact_n;
    setup := BD8_Setup(k);
    fact_n := Factorial(4 * k);
    t0 := Runtime();
    if not IsBound(BD8_EnumerateUorbitsV2) then
        Read("C:/Users/jeffr/Downloads/Lifting/b_d8_v2.g");
    fi;
    BD8_ResetCCache();
    if IsExistingFile(Concatenation(
            "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits/k",
            String(k), ".g")) then
        U_orbits := BD8_LoadUOrbits(setup, Concatenation(
            "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits/k",
            String(k), ".g"));
    else
        U_orbits := BD8_EnumerateUorbitsV2(setup);
    fi;
    class_sum := 0;
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        U_dim := Dimension(U_rec.U);
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            C_dim := Dimension(C_rec.C);
            L_dim := U_dim * (Dimension(setup.Z) - C_dim);
            contrib := fact_n * 2^L_dim / (8^k * Length(C_rec.stab));
            class_sum := class_sum + contrib;
        od;
        if Runtime() - t_hb >= 15000 or u_idx = Length(U_orbits) then
            Print("[BD8uc] k=", k, "  u=", u_idx, "/", Length(U_orbits),
                  "  cs_so_far=", class_sum,
                  "  (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    return rec(class_sum := class_sum, elapsed_ms := Runtime() - t0);
end;

# BD8_ClassSumOnly(k)
#   Pure count: returns rec(count, class_sum) without materializing any
#   generators or touching the filesystem.  For producing labelled-subgroup
#   contributions when the persisted gens are not needed.
BD8_ClassSumOnly := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, t0, t_hb, u_idx,
          lift_res, NG_size, stab_sk, cs, class_sum, total, fact_n, j;
    setup := BD8_Setup(k);
    fact_n := Factorial(4 * k);
    t0 := Runtime();
    if not IsBound(BD8_EnumerateUorbitsV2) then
        Read("C:/Users/jeffr/Downloads/Lifting/b_d8_v2.g");
    fi;
    BD8_ResetCCache();
    if IsExistingFile(Concatenation(
            "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits/k",
            String(k), ".g")) then
        U_orbits := BD8_LoadUOrbits(setup, Concatenation(
            "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits/k",
            String(k), ".g"));
    else
        U_orbits := BD8_EnumerateUorbitsV2(setup);
    fi;
    class_sum := 0;
    total := 0;
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            lift_res := BD8_LiftOrbitRepsH(setup, U_rec, C_rec);
            NG_size := 8^k / 2^lift_res.dim_R;
            for j in [1..Length(lift_res.reps)] do
                stab_sk := Length(C_rec.stab) / lift_res.orbit_lens[j];
                cs := fact_n / (NG_size * stab_sk);
                class_sum := class_sum + cs;
                total := total + 1;
            od;
        od;
        if Runtime() - t_hb >= 30000 or u_idx = Length(U_orbits) then
            Print("[BD8s] k=", k, "  u=", u_idx, "/", Length(U_orbits),
                  "  reps=", total, "  cs_sum=", class_sum,
                  "  (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    return rec(count := total, class_sum := class_sum,
               elapsed_ms := Runtime() - t0);
end;

# WriteBD8FileWithCS(k, output_path)
#   Same as WriteBD8File but additionally emits
#     # class_sum: S
#     # class_sizes: c1,c2,...
#   computed via the validated harvest formula.
WriteBD8FileWithCS := function(k, output_path)
    local setup, blocks, U_orbits, U_rec, C_orbits, C_rec, t0, fout,
          total, all_triples, lift_res, gens, u_idx, t_hb,
          combo_pairs, write_idx, u_cache_path, u_cache_dir, NG_size,
          stab_sk, cs, class_sizes, class_sum, n_total, fact_n, j;
    setup := BD8_Setup(k);
    blocks := BD8_BlockData(k);
    n_total := 4 * k;
    fact_n := Factorial(n_total);
    t0 := Runtime();
    Print("[BD8h] k=", k, " starting (output ", output_path, ")\n");
    if not IsBound(BD8_EnumerateUorbitsV2) then
        Read("C:/Users/jeffr/Downloads/Lifting/b_d8_v2.g");
    fi;
    BD8_ResetCCache();
    u_cache_dir := "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits";
    u_cache_path := Concatenation(u_cache_dir, "/k", String(k), ".g");
    if IsExistingFile(u_cache_path) then
        U_orbits := BD8_LoadUOrbits(setup, u_cache_path);
    else
        U_orbits := BD8_EnumerateUorbitsV2(setup);
        Exec(Concatenation("mkdir -p \"", u_cache_dir, "\""));
        BD8_SaveUOrbits(setup, U_orbits, u_cache_path);
    fi;
    Print("[BD8h] U orbits: ", Length(U_orbits), "\n");

    # Enumerate all (U, C, ell, orbit_len, NG_size) tuples.
    #   NG_size = 8^k / 2^{dim R}  is constant over a (U,C) -- closed form,
    #   no Normalizer call.
    all_triples := [];
    class_sizes := [];
    class_sum := 0;
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            lift_res := BD8_LiftOrbitRepsH(setup, U_rec, C_rec);
            NG_size := 8^setup.k / 2^lift_res.dim_R;
            for j in [1..Length(lift_res.reps)] do
                stab_sk := Length(C_rec.stab) / lift_res.orbit_lens[j];
                cs := fact_n / (NG_size * stab_sk);
                Add(all_triples, [U_rec, C_rec, lift_res.reps[j]]);
                Add(class_sizes, cs);
                class_sum := class_sum + cs;
            od;
        od;
        if Runtime() - t_hb >= 30000 or u_idx = Length(U_orbits) then
            Print("[BD8h] enumerate u=", u_idx, "/", Length(U_orbits),
                  " triples=", Length(all_triples),
                  " cs_so_far=", class_sum,
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    total := Length(all_triples);
    Print("[BD8h] total reps: ", total, "  cs_sum=", class_sum,
          "  (elapsed_ms=", Runtime() - t0, ")\n");

    # Pass 2: materialize gens to a temp file (cs is already computed).
    t_hb := Runtime();
    fout := OutputTextFile(Concatenation(output_path, ".tmpgens"), false);
    SetPrintFormattingStatus(fout, false);
    for write_idx in [1..total] do
        gens := BD8_MaterializeTriple(setup, blocks,
            all_triples[write_idx][1], all_triples[write_idx][2],
            all_triples[write_idx][3]);
        PrintTo(fout, BD8_FormatGenList(gens), "\n");
        if Runtime() - t_hb >= 30000 or write_idx = total then
            Print("[BD8h] materialized ", write_idx, "/", total,
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    CloseStream(fout);

    # Pass 2: compose final file with headers (now we have class_sum).
    fout := OutputTextFile(output_path, false);
    SetPrintFormattingStatus(fout, false);
    combo_pairs := List([1..k], i -> [4, 3]);
    PrintTo(fout, "# combo: ", combo_pairs, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", Runtime() - t0, "\n");
    PrintTo(fout, "# class_sum: ", class_sum, "\n");
    PrintTo(fout, "# class_sizes: ",
            JoinStringsWithSeparator(List(class_sizes, String), ","), "\n");
    AppendTo(fout, StringFile(Concatenation(output_path, ".tmpgens")));
    CloseStream(fout);
    RemoveFile(Concatenation(output_path, ".tmpgens"));
    Print("[BD8h] Wrote ", output_path, "  class_sum=", class_sum, "\n");
    return rec(count := total, class_sum := class_sum,
               class_sizes := class_sizes);
end;
