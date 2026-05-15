################################################################################
# b_d8.g
#
# Frattini-factor enumeration of FPF subgroup conjugacy classes for D_8^k
# (= [4,3]^k in transitive-group notation).
#
# Math:
#   G = D_8^k, Z = Z(G) = Phi(G) = G' ~= F_2^k, Q = G/Z ~= F_2^{2k}.
#   q: Q -> Z, block-wise q(a,b) = a*(1+b) in F_2 (asymmetric quadratic).
#   B: Q x Q -> Z, B((a,b),(c,d)) = ad+bc in F_2 (block symplectic).
#
# Each subgroup H <= G corresponds to a triple (U, C, ell) where:
#   U = HZ/Z <= Q
#   C = H n Z <= Z, with q(U) subset C
#   ell in Hom(U, Z/C) / R    where R = {u -> B(w, u): w in Q} subspace of L
# and the (D_8 wr S_k)-conjugacy class corresponds to the S_k-orbit of (U, C, ell).
################################################################################

# Setup record: precompute F_2 ambient spaces and block-projection data.
BD8_Setup := function(k)
    local F, Q, Z, e_Q, e_Z, blk_a, blk_b;
    F := GF(2);
    Q := F^(2*k);
    Z := F^k;
    e_Q := Basis(Q);  # 2k standard basis vectors
    e_Z := Basis(Z);  # k standard basis vectors
    # blk_a[i], blk_b[i] = standard basis vectors at block i positions 1, 2
    blk_a := List([1..k], i -> e_Q[2*i-1]);
    blk_b := List([1..k], i -> e_Q[2*i]);
    return rec(F := F, k := k, Q := Q, Z := Z,
               blk_a := blk_a, blk_b := blk_b, e_Z := e_Z);
end;

# Quadratic q: Q -> Z. q(u) at block i = u[2i-1] * (1 + u[2i]) in F_2.
BD8_q := function(setup, u)
    local i, a, b, result;
    result := List([1..setup.k], i -> Zero(setup.F));
    for i in [1..setup.k] do
        a := u[2*i - 1]; b := u[2*i];
        result[i] := a + a*b;
    od;
    return result * One(setup.F);
end;

# Bilinear B: Q x Q -> Z, B(u,v) at block i = u[2i-1]*v[2i] + u[2i]*v[2i-1].
BD8_B := function(setup, u, v)
    local i, result;
    result := List([1..setup.k], i -> Zero(setup.F));
    for i in [1..setup.k] do
        result[i] := u[2*i-1] * v[2*i] + u[2*i] * v[2*i-1];
    od;
    return result * One(setup.F);
end;

# S_k action on Q: permute blocks via sigma in Sym(k).
BD8_PermQ := function(setup, sigma, u)
    local v, i, ip;
    v := ListWithIdenticalEntries(2*setup.k, Zero(setup.F));
    for i in [1..setup.k] do
        ip := i ^ sigma;
        v[2*ip - 1] := u[2*i - 1];
        v[2*ip]     := u[2*i];
    od;
    return v * One(setup.F);
end;

BD8_PermZ := function(setup, sigma, z)
    local w, i;
    w := ListWithIdenticalEntries(setup.k, Zero(setup.F));
    for i in [1..setup.k] do
        w[i^sigma] := z[i];
    od;
    return w * One(setup.F);
end;

# Apply sigma to a subspace by mapping its basis.
BD8_PermSubspaceQ := function(setup, sigma, U)
    return Subspace(setup.Q,
        List(Basis(U), v -> BD8_PermQ(setup, sigma, v)));
end;

BD8_PermSubspaceZ := function(setup, sigma, C)
    return Subspace(setup.Z,
        List(Basis(C), v -> BD8_PermZ(setup, sigma, v)));
end;

# ---- subdirect check: each block projection is rank 2 ------------------------
BD8_IsSubdirect := function(setup, U)
    local i, projs, v;
    for i in [1..setup.k] do
        projs := List(Basis(U), v -> [v[2*i-1], v[2*i]]);
        # Check rank 2 over F_2.  projs lives in F_2^2, max rank 2.
        if RankMat(projs * One(setup.F)) < 2 then return false; fi;
    od;
    return true;
end;

# ---- canonical U under S_k brute force --------------------------------------
# Canonical form = reduced row-echelon basis (sorted rows), lex-min over S_k.
# Basis is O(r) vectors rather than 2^r elements -> much faster than full
# AsList(U) approach.
BD8_EchelonBasis := function(setup, vecs)
    local mat;
    if Length(vecs) = 0 then return []; fi;
    mat := MutableCopyMat(vecs);
    TriangulizeMat(mat);
    return SortedList(Filtered(mat, v -> not IsZero(v)));
end;

BD8_CanonicalU := function(setup, U, Sk_list)
    local sigma, best, U_basis, image_basis;
    U_basis := AsList(Basis(U));
    best := fail;
    for sigma in Sk_list do
        image_basis := BD8_EchelonBasis(setup,
            List(U_basis, v -> BD8_PermQ(setup, sigma, v)));
        if best = fail or image_basis < best then
            best := image_basis;
        fi;
    od;
    return best;
end;

# ---- enumerate subdirect U orbits mod S_k -----------------------------------
# Enumerate all subspaces of Q of each dim, filter subdirect, canonicalize,
# bucket.
BD8_EnumerateUorbits := function(setup)
    local k, Q, keys, results, dim, U, canon, pos, Sk_list, stab_U,
          n_total, n_subdirect, t_hb, hb_interval_ms, n_dim;
    k := setup.k;
    Q := setup.Q;
    Sk_list := AsList(SymmetricGroup(k));
    keys := [];
    results := [];
    n_total := 0;
    n_subdirect := 0;
    t_hb := Runtime();
    hb_interval_ms := 30000;  # 30s heartbeat
    Print("[BD8_U] starting subspace enumeration, |S_", k, "|=",
          Length(Sk_list), "\n");
    for dim in [2*k, 2*k-1..2] do
        n_dim := 0;
        for U in Subspaces(Q, dim) do
            n_total := n_total + 1;
            n_dim := n_dim + 1;
            if Runtime() - t_hb >= hb_interval_ms then
                Print("[BD8_U] hb total=", n_total, " subdir=",
                      n_subdirect, " orbits=", Length(results),
                      " dim=", dim, " dim_done=", n_dim,
                      " (", Runtime(), "ms)\n");
                t_hb := Runtime();
            fi;
            if not BD8_IsSubdirect(setup, U) then continue; fi;
            n_subdirect := n_subdirect + 1;
            canon := BD8_CanonicalU(setup, U, Sk_list);
            pos := PositionSorted(keys, canon);
            if pos > Length(keys) or keys[pos] <> canon then
                Add(keys, canon, pos);
                stab_U := Filtered(Sk_list,
                    sigma -> BD8_PermSubspaceQ(setup, sigma, U) = U);
                Add(results, rec(U := U, stab := stab_U, dim := dim), pos);
            fi;
        od;
        Print("[BD8_U] dim=", dim, " done: subspaces=", n_dim,
              " orbits_total=", Length(results), "\n");
    od;
    Print("[BD8_U] enumeration complete: ", n_total, " subspaces, ",
          n_subdirect, " subdirect, ", Length(results), " orbits\n");
    return results;
end;

# ---- U-orbit persistence to disk --------------------------------------------
# Format: a .g file that sets BD8_LOADED_U_ORBITS_RAW := [rec(basis, perms, dim), ...].
# basis is a list of int-encoded F_2 vectors; perms is a list of S_k images
# as lists [i^sigma for i in 1..k].  Reconstructed via BD8_LoadUOrbits(setup, path).
BD8_SaveUOrbits := function(setup, U_orbits, path)
    local f, U_rec, basis_vecs, perm_lists;
    f := OutputTextFile(path, false);
    SetPrintFormattingStatus(f, false);
    PrintTo(f, "# BD8 U-orbits k=", setup.k, " count=", Length(U_orbits), "\n");
    PrintTo(f, "BD8_LOADED_U_ORBITS_RAW := [\n");
    for U_rec in U_orbits do
        basis_vecs := List(AsList(Basis(U_rec.U)), v -> List(v, IntFFE));
        perm_lists := List(U_rec.stab,
            sigma -> List([1..setup.k], i -> i^sigma));
        PrintTo(f, "rec(basis:=", basis_vecs,
                ",perms:=", perm_lists,
                ",dim:=", U_rec.dim, "),\n");
    od;
    PrintTo(f, "];\n");
    CloseStream(f);
end;
BD8_LoadUOrbits := function(setup, path)
    local U_orbits, raw_rec, basis, stab;
    Unbind(BD8_LOADED_U_ORBITS_RAW);
    Read(path);
    U_orbits := [];
    for raw_rec in BD8_LOADED_U_ORBITS_RAW do
        basis := raw_rec.basis * One(setup.F);
        stab := List(raw_rec.perms, l -> PermList(l));
        Add(U_orbits, rec(
            U := Subspace(setup.Q, basis),
            stab := stab,
            dim := raw_rec.dim));
    od;
    Unbind(BD8_LOADED_U_ORBITS_RAW);
    return U_orbits;
end;

# ---- compute C_min = span(q(U)) ----------------------------------------------
# OPTIMIZATION: q(u+v) = q(u) + q(v) + B(u,v) over F_2, so Cmin is spanned by
# q(u_i) for basis u_i + B(u_i, u_j) for i<j.  Avoids 2^dim(U) iteration.
BD8_Cmin := function(setup, U)
    local basis_U, gens, i, j, d;
    basis_U := AsList(Basis(U));
    d := Length(basis_U);
    gens := [];
    for i in [1..d] do
        Add(gens, BD8_q(setup, basis_U[i]));
        for j in [i+1..d] do
            Add(gens, BD8_B(setup, basis_U[i], basis_U[j]));
        od;
    od;
    return Subspace(setup.Z, gens);
end;

# ---- C-orbit cache by (Stab(U), Cmin) ---------------------------------------
# C-enumeration depends only on Stab(U) (acts on Z by permuting coords) and
# Cmin ⊆ Z (the floor).  Many U-orbits share the same (Stab, Cmin), so cache.
BD8_C_ORBIT_CACHE := fail;   # NewDictionary, initialized by ResetCCache.
BD8_C_CACHE_HITS := 0;
BD8_C_CACHE_MISSES := 0;
BD8_ResetCCache := function()
    BD8_C_ORBIT_CACHE := NewDictionary("", true);
    BD8_C_CACHE_HITS := 0;
    BD8_C_CACHE_MISSES := 0;
end;
BD8_StabKey := function(stab_list)
    return SortedList(stab_list);
end;
BD8_SubspaceKey := function(V)
    local b;
    b := MutableCopyMat(AsList(Basis(V)));
    TriangulizeMat(b);
    return SortedList(b);
end;

# ---- enumerate C with Cmin <= C <= Z, mod Stab(U) ---------------------------
# Stab is given as a list of S_k elements.  Cached on (Stab, Cmin) keys.
BD8_EnumerateCorbits := function(setup, U_rec)
    local Cmin, C, results, seen_keys, canon, sigma, image, key,
          perm_stab, pos, stab_key, cmin_key, cache_key, cached;
    Cmin := BD8_Cmin(setup, U_rec.U);
    stab_key := BD8_StabKey(U_rec.stab);
    cmin_key := BD8_SubspaceKey(Cmin);
    cache_key := [stab_key, cmin_key];
    cached := LookupDictionary(BD8_C_ORBIT_CACHE, cache_key);
    if cached <> fail then
        BD8_C_CACHE_HITS := BD8_C_CACHE_HITS + 1;
        return cached;
    fi;
    BD8_C_CACHE_MISSES := BD8_C_CACHE_MISSES + 1;
    seen_keys := [];
    results := [];
    for C in Subspaces(setup.Z) do
        if not IsSubset(C, Cmin) then continue; fi;
        canon := fail;
        for sigma in U_rec.stab do
            image := BD8_PermSubspaceZ(setup, sigma, C);
            key := SortedList(AsList(image));
            if canon = fail or key < canon then canon := key; fi;
        od;
        pos := PositionSorted(seen_keys, canon);
        if pos > Length(seen_keys) or seen_keys[pos] <> canon then
            Add(seen_keys, canon, pos);
            perm_stab := Filtered(U_rec.stab,
                sigma -> BD8_PermSubspaceZ(setup, sigma, C) = C);
            Add(results, rec(C := C, stab := perm_stab,
                              C_dim := Dimension(C)), pos);
        fi;
    od;
    AddDictionary(BD8_C_ORBIT_CACHE, cache_key, results);
    return results;
end;

# ---- compute |E| = |Hom(U, Z/C)/R| and count orbits under Stab(U,C) ---------
# For each ell in E, count its Stab(U,C)-orbit, sum 1/|orbit| (Burnside).
# Or: just enumerate orbits and count.
# Returns: rec(count, reps) where reps is a list of E representatives (each a
# flat F_2-vector of length L_dim) -- one per Stab(U,C)-orbit in E = L/R.
BD8_LiftOrbitReps := function(setup, U_rec, C_rec)
    local U, C, U_dim, C_dim, ZC_dim, L_dim, basis_U, hom_ZC, basis_ZC,
          basis_ZC_lifts, R_basis, w, ell_w, L, R, E_size, sigma, sigma_inv,
          M, N, action, e_canon, e_reps_keys, e_reps, idx, i, j, v,
          perm_list, sig_perm, orbits, L_list, r_red, orbit_reps, hom_LR;
    U := U_rec.U;
    C := C_rec.C;
    U_dim := Dimension(U);
    C_dim := Dimension(C);
    ZC_dim := Dimension(setup.Z) - C_dim;
    L_dim := U_dim * ZC_dim;
    if L_dim = 0 then
        # Trivial L: only empty representative.
        return rec(count := 1, reps := [[]]);
    fi;

    basis_U := AsList(Basis(U));
    hom_ZC := NaturalHomomorphismBySubspace(setup.Z, C);
    basis_ZC := AsList(Basis(Range(hom_ZC)));
    basis_ZC_lifts := List(basis_ZC,
        b -> PreImagesRepresentative(hom_ZC, b));

    L := setup.F^L_dim;
    R_basis := [];
    # OPTIMIZATION: ell_w(u) = B(w,u) mod C is linear in w (B bilinear), so
    # R = span{ell_w : w in basis(Q)} suffices.  2k vectors vs 2^(2k).
    for w in Basis(setup.Q) do
        ell_w := Concatenation(List(basis_U, u ->
            AsList(Image(hom_ZC, BD8_B(setup, w, u)))));
        Add(R_basis, ell_w * One(setup.F));
    od;
    R := Subspace(L, R_basis);
    E_size := Size(L) / Size(R);
    r_red := SemiEchelonBasis(R);
    e_canon := function(v_in)
        return SiftedVector(r_red, v_in);
    end;
    # OPTIMIZED: enumerate L/R coset reps directly via NHB, instead of
    # iterating all 2^L_dim elements of L.  For each q in L/R, take its
    # canonical preimage in L (sifted mod R).
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
        return rec(count := E_size, reps := e_reps);
    fi;

    # Build sigma-permutation on e_reps.
    perm_list := [];
    for sigma in C_rec.stab do
        sigma_inv := Inverse(sigma);
        M := List(basis_U, u_i -> SolutionMat(basis_U,
            BD8_PermQ(setup, sigma_inv, u_i))) * One(setup.F);
        N := List(basis_ZC_lifts,
            b -> AsList(Image(hom_ZC, BD8_PermZ(setup, sigma, b))))
            * One(setup.F);
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
            return e_canon(result * One(setup.F));
        end;
        sig_perm := PermList(List(e_reps,
            r -> PositionSorted(e_reps_keys, action(r))));
        Add(perm_list, sig_perm);
    od;
    orbits := Orbits(Group(perm_list, ()), [1..Length(e_reps)]);
    orbit_reps := List(orbits, o -> e_reps[o[1]]);
    return rec(count := Length(orbits), reps := orbit_reps);
end;

# Backwards-compat thin wrapper for counting only.
BD8_CountLiftOrbits := function(setup, U_rec, C_rec)
    return BD8_LiftOrbitReps(setup, U_rec, C_rec).count;
end;

# ---- materializer: (U, C, ell) -> permutation generators of H <= S_{4k} ----
# Picks r_T (order-4 element) and s_T (order-2 element outside <r_T>) from
# TransitiveGroup(4, 3), then for each block i sets:
#   r_i = r_T shifted to block i, s_i = s_T shifted, z_i = r_i^2 (central).
# u in F_2^{2k} with block-i bits (a_i, b_i) lifts to r_i^{a_i} s_i^{b_i}.
# Central z in F_2^k with bit i = 1 lifts to product of z_i's.
BD8_BlockData := function(k)
    local T, elts, r_T, s_T, blocks, i, shift;
    T := TransitiveGroup(4, 3);
    elts := AsList(T);
    r_T := First(elts, x -> Order(x) = 4);
    s_T := First(elts, x -> Order(x) = 2 and not (x in Group([r_T])));
    if s_T = fail then Error("could not find s_T in D_8"); fi;
    blocks := [];
    for i in [1..k] do
        shift := MappingPermListList([1..4], [4*(i-1)+1 .. 4*i]);
        Add(blocks, rec(r := r_T ^ shift, s := s_T ^ shift,
                        z := (r_T^2) ^ shift));
    od;
    return blocks;
end;

BD8_LiftU := function(setup, blocks, u)
    local result, i, a, b;
    result := ();
    for i in [1..setup.k] do
        a := u[2*i - 1]; b := u[2*i];
        if a = One(setup.F) then result := result * blocks[i].r; fi;
        if b = One(setup.F) then result := result * blocks[i].s; fi;
    od;
    return result;
end;

BD8_LiftZ := function(setup, blocks, z)
    local result, i;
    result := ();
    for i in [1..setup.k] do
        if z[i] = One(setup.F) then result := result * blocks[i].z; fi;
    od;
    return result;
end;

BD8_MaterializeTriple := function(setup, blocks, U_rec, C_rec, ell_flat)
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
        h_j := BD8_LiftU(setup, blocks, basis_U[j]) *
               BD8_LiftZ(setup, blocks, ell_j_lift);
        Add(gens, h_j);
    od;
    for c in basis_C do
        Add(gens, BD8_LiftZ(setup, blocks, c));
    od;
    return gens;
end;

BD8_FormatGenList := function(gens)
    return Concatenation("[",
        JoinStringsWithSeparator(List(gens, g -> String(g)), ","),
        "]");
end;

# Top-level enumerate + materialize + write standard combo-file format.
WriteBD8File := function(k, output_path)
    local setup, blocks, U_orbits, U_rec, C_orbits, C_rec, t0, fout,
          total, all_triples, lift_res, ell_rep, gens, line, u_idx, t_hb,
          n_triples, combo_pairs, write_idx, u_cache_path, u_cache_dir;
    setup := BD8_Setup(k);
    blocks := BD8_BlockData(k);
    t0 := Runtime();
    Print("[BD8w] k=", k, " starting (output ", output_path, ")\n");
    if not IsBound(BD8_EnumerateUorbitsV2) then
        Read("C:/Users/jeffr/Downloads/Lifting/b_d8_v2.g");
    fi;
    BD8_ResetCCache();
    u_cache_dir := "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits";
    u_cache_path := Concatenation(u_cache_dir, "/k", String(k), ".g");
    if IsExistingFile(u_cache_path) then
        Print("[BD8w] loading U orbits from ", u_cache_path, "\n");
        U_orbits := BD8_LoadUOrbits(setup, u_cache_path);
        Print("[BD8w] loaded ", Length(U_orbits), " U orbits (load_ms=",
              Runtime() - t0, ")\n");
    else
        U_orbits := BD8_EnumerateUorbitsV2(setup);
        Print("[BD8w] U orbits: ", Length(U_orbits),
              " (enum_ms=", Runtime() - t0, ")\n");
        Exec(Concatenation("mkdir -p \"", u_cache_dir, "\""));
        BD8_SaveUOrbits(setup, U_orbits, u_cache_path);
        Print("[BD8w] saved U orbits to ", u_cache_path, "\n");
    fi;
    # First pass: enumerate all triples and total count, then write.
    all_triples := [];
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            lift_res := BD8_LiftOrbitReps(setup, U_rec, C_rec);
            for ell_rep in lift_res.reps do
                Add(all_triples, [U_rec, C_rec, ell_rep]);
            od;
        od;
        if Runtime() - t_hb >= 30000 or u_idx = Length(U_orbits) then
            Print("[BD8w] enumerate u=", u_idx, "/", Length(U_orbits),
                  " triples=", Length(all_triples),
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    total := Length(all_triples);
    Print("[BD8w] total reps: ", total,
          " (enum+orbit_ms=", Runtime() - t0, ")\n");

    fout := OutputTextFile(output_path, false);
    SetPrintFormattingStatus(fout, false);
    combo_pairs := List([1..k], i -> [4, 3]);
    PrintTo(fout, "# combo: ", combo_pairs, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", Runtime() - t0, "\n");
    t_hb := Runtime();
    for write_idx in [1..total] do
        gens := BD8_MaterializeTriple(setup, blocks,
            all_triples[write_idx][1], all_triples[write_idx][2],
            all_triples[write_idx][3]);
        PrintTo(fout, BD8_FormatGenList(gens), "\n");
        if Runtime() - t_hb >= 30000 or write_idx = total then
            Print("[BD8w] materialized ", write_idx, "/", total,
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    CloseStream(fout);
    Print("[BD8w] Wrote ", output_path, "\n");
    return total;
end;

# ---- top-level: count [4,3]^k FPF subgroup conjugacy classes -----------------
BD8_CountAll := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, total, contrib,
          u_idx, t0, t_hb, t_u, lift_total;
    setup := BD8_Setup(k);
    t0 := Runtime();
    Print("[BD8] k=", k, " starting\n");
    BD8_ResetCCache();
    U_orbits := BD8_EnumerateUorbits(setup);
    Print("[BD8] U orbits (subdirect, mod S_", k, "): ",
          Length(U_orbits), " (enum_ms=", Runtime() - t0, ")\n");
    total := 0;
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        t_u := Runtime();
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        lift_total := 0;
        for C_rec in C_orbits do
            contrib := BD8_CountLiftOrbits(setup, U_rec, C_rec);
            lift_total := lift_total + contrib;
        od;
        total := total + lift_total;
        if Runtime() - t_hb >= 30000 or u_idx = Length(U_orbits) then
            Print("[BD8] u_idx=", u_idx, "/", Length(U_orbits),
                  " dim=", U_rec.dim, " stab=", Length(U_rec.stab),
                  " Cs=", Length(C_orbits), " contrib=", lift_total,
                  " total=", total, " (u_ms=", Runtime() - t_u,
                  " elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    return total;
end;
