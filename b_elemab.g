################################################################################
# b_elemab.g
#
# Generalization of b21_support_first.g from (p=2, m=1) to arbitrary
# elementary abelian factors T = (Z/p)^m. Enumerates orbit reps of subdirect
# subgroups H <= T^k under GL_m(F_p) wr S_k acting on F_p^{mk}.
#
# Math: H corresponds to an F_p-subspace V <= F_p^{mk} with each m-block
# projection surjective. By absorbing the within-block GL_m action, V's
# orbit is captured by the multiset {W_1, ..., W_k} where W_i = column-span
# of the i-th block of any generator matrix of V, viewed as a subspace of
# F_p^r (where r = dim V). The remaining equivalence is the GL_r(F_p)
# action on subspaces, combined with S_k permuting the multiset entries.
#
# Algorithm: support-first enumeration of multisets of m-dim subspaces of
# F_p^r whose union spans F_p^r, modulo GL_r(F_p). For each support, count
# Aut(S)-orbits on positive-integer compositions of k into |S| parts.
#
# (p=2, m=1) recovers b21 exactly.
################################################################################

# ------------------------------------------------------------------ encoding
# Encode F_p^r vectors as integers in [1..p^r - 1] (zero = 0).
ELEMAB_VecEncode := function(p, r, v)
    local s, i;
    s := 0;
    for i in [r,r-1..1] do
        s := s * p + IntFFE(v[i]);
    od;
    return s;
end;

ELEMAB_VecDecode := function(p, r, enc)
    local v, x, i;
    v := []; x := enc;
    for i in [1..r] do
        Add(v, x mod p);
        x := QuoInt(x, p);
    od;
    return v * One(GF(p));
end;

# ----------------------------------------------------- GL_r(F_p) as perm group
ELEMAB_GLR_CACHE := rec();
ELEMAB_GetGLrAsPermGroup := function(p, r)
    local key, n, V, gens, perms;
    key := Concatenation(String(p), "_", String(r));
    if IsBound(ELEMAB_GLR_CACHE.(key)) then
        return ELEMAB_GLR_CACHE.(key);
    fi;
    n := p^r - 1;
    V := List([1..n], e -> ELEMAB_VecDecode(p, r, e));
    gens := GeneratorsOfGroup(GL(r, p));
    perms := List(gens, g -> PermList(List([1..n], i ->
        ELEMAB_VecEncode(p, r, V[i] * g))));
    ELEMAB_GLR_CACHE.(key) := Group(perms);
    return ELEMAB_GLR_CACHE.(key);
end;

# ------------------------------------ all m-dim subspaces of F_p^r as int-sets
# Each m-dim subspace W has p^m - 1 nonzero elements. Represent as
# Set of encodings.
ELEMAB_AllMDimSubspaceSets := function(p, r, m)
    local subs, sets;
    if r < m then return []; fi;
    subs := AsList(Subspaces(GF(p)^r, m));
    sets := List(subs, W -> Set(
        List(Filtered(AsList(W), v -> not IsZero(v)),
             v -> ELEMAB_VecEncode(p, r, v))));
    # Sort so PositionSorted gives O(log n) index lookup.
    Sort(sets);
    return sets;
end;

# Action of GL_r-as-perm on a subspace-set.
ELEMAB_OnSubspaceSet := function(W_set, g)
    return Set(List(W_set, e -> e^g));
end;

# Build the permutation action of GL_r on the index set of m-dim subspaces.
ELEMAB_SUBS_CACHE := rec();
ELEMAB_GLrOnSubspaces := function(p, r, m)
    local key, glr, all_subs, n_subs, gens_perm;
    key := Concatenation(String(p), "_", String(r), "_", String(m));
    if IsBound(ELEMAB_SUBS_CACHE.(key)) then
        return ELEMAB_SUBS_CACHE.(key);
    fi;
    glr := ELEMAB_GetGLrAsPermGroup(p, r);
    all_subs := ELEMAB_AllMDimSubspaceSets(p, r, m);
    n_subs := Length(all_subs);
    gens_perm := List(GeneratorsOfGroup(glr), g ->
        PermList(List([1..n_subs], i ->
            PositionSorted(all_subs,
                           ELEMAB_OnSubspaceSet(all_subs[i], g)))));
    ELEMAB_SUBS_CACHE.(key) := rec(
        all_subs := all_subs,
        n_subs := n_subs,
        group_on_indices := Group(gens_perm, ())
    );
    return ELEMAB_SUBS_CACHE.(key);
end;

# Span (as F_p-subspace) of a list of m-dim subspaces given by their
# nonzero-vector-encoding sets. Returns dimension (rank).
ELEMAB_UnionRank := function(p, r, m, S, all_subs)
    local mat, idx, e, v;
    if Length(S) = 0 then return 0; fi;
    mat := [];
    for idx in S do
        for e in all_subs[idx] do
            Add(mat, ELEMAB_VecDecode(p, r, e));
        od;
    od;
    return RankMat(mat * One(GF(p)));
end;

# Cheap GL_r-invariant hash of a multiset of subspace indices.
# Combines:
#  - rank-distribution: for each k' in [1..|S|], multiset of dim(span of
#    k'-subsets of S).
#  - dual histogram: for each hyperplane H of F_p^r, count of W in S with
#    W <= H. Represented as a sorted multiset (which is GL_r-invariant).
ELEMAB_SubsetHash := function(S, p, r, m, all_subs)
    local n, hash, k, sub, mat, ranks, hyperplanes,
          counts_per_hp, H, count, idx;
    n := Length(S);
    if n = 0 then return [0]; fi;
    hash := [n];
    # rank-distribution
    for k in [1..n] do
        ranks := [];
        for sub in Combinations([1..n], k) do
            Add(ranks, ELEMAB_UnionRank(p, r, m,
                                         List(sub, i -> S[i]),
                                         all_subs));
        od;
        Sort(ranks);
        Add(hash, ranks);
    od;
    # dual histogram (only for small r to keep it cheap)
    if r <= 8 then
        hyperplanes := AsList(Subspaces(GF(p)^r, r - 1));
        counts_per_hp := [];
        for H in hyperplanes do
            count := 0;
            for idx in S do
                # W <= H iff every nonzero element of W is in H
                if ForAll(all_subs[idx], e ->
                    ELEMAB_VecDecode(p, r, e) in H)
                then
                    count := count + 1;
                fi;
            od;
            Add(counts_per_hp, count);
        od;
        Sort(counts_per_hp);
        Add(hash, counts_per_hp);
    fi;
    return hash;
end;

# Multiplicity orbits via Aut_S on positive compositions of k.
# Aut_S = stabilizer of S in GL_r-on-indices, viewed as its permutation
# action on the index list [1..|S|].
ELEMAB_StabAsPermOnSet := function(A, S, glr_on_subs_rec)
    local n, gens, g, perm_list, j, target_idx;
    n := Length(S);
    if n = 0 then return SymmetricGroup(0); fi;
    if Size(A) = 1 then return Group((), ()); fi;
    gens := [];
    for g in GeneratorsOfGroup(A) do
        perm_list := [];
        for j in [1..n] do
            target_idx := S[j] ^ g;
            Add(perm_list, Position(S, target_idx));
        od;
        Add(gens, PermList(perm_list));
    od;
    return Group(gens, ());
end;

ELEMAB_MultOrbits := function(A_perm, n_S, k)
    local compositions, orbs;
    if k < n_S then return []; fi;
    compositions := OrderedPartitions(k, n_S);  # positive parts only
    if Length(compositions) = 0 then return []; fi;
    orbs := OrbitsDomain(A_perm, compositions, Permuted);
    return List(orbs, o -> o[1]);
end;

# ------------------------------------------- main: support-first enumeration
# Enumerate orbit reps of size-up-to-max_size supports of m-dim subspaces of
# F_p^r (multisets, modulo GL_r). Returns list of records {S, A, A_perm}.
ELEMAB_EnumerateSupports := function(p, m, r, max_size)
    local rec_data, n_subs, all_subs, glr_on_idx, R_curr, R_next, t, S_data,
          S, A, ext_orbs, orb, p_new, T, h, hash_keys, hash_buckets,
          bucket_idx, bucket, found, R_T, A_T, A_T_perm, results;
    rec_data := ELEMAB_GLrOnSubspaces(p, r, m);
    all_subs := rec_data.all_subs;
    n_subs := rec_data.n_subs;
    glr_on_idx := rec_data.group_on_indices;
    R_curr := [rec(S := [],
                   A := glr_on_idx,
                   A_perm := SymmetricGroup(0))];
    results := [];
    for t in [0..max_size - 1] do
        R_next := [];
        hash_keys := [];
        hash_buckets := [];
        for S_data in R_curr do
            S := S_data.S;
            A := S_data.A;
            ext_orbs := OrbitsDomain(A, Difference([1..n_subs], S), OnPoints);
            for orb in ext_orbs do
                p_new := orb[1];
                T := SortedList(Concatenation(S, [p_new]));
                h := ELEMAB_SubsetHash(T, p, r, m, all_subs);
                bucket_idx := PositionSorted(hash_keys, h);
                if bucket_idx <= Length(hash_keys)
                    and hash_keys[bucket_idx] = h then
                    bucket := hash_buckets[bucket_idx];
                else
                    Add(hash_keys, h, bucket_idx);
                    Add(hash_buckets, [], bucket_idx);
                    bucket := hash_buckets[bucket_idx];
                fi;
                # GL_r-equivalence within bucket via RepresentativeAction
                # OnSets: setwise (T has no duplicates since p_new is new).
                found := false;
                for R_T in bucket do
                    if RepresentativeAction(glr_on_idx, R_T.T, T, OnSets)
                        <> fail then
                        found := true; break;
                    fi;
                od;
                if not found then
                    Add(bucket, rec(T := T));
                    A_T := Stabilizer(glr_on_idx, T, OnSets);
                    A_T_perm := ELEMAB_StabAsPermOnSet(A_T, T, rec_data);
                    Add(R_next, rec(S := T, A := A_T, A_perm := A_T_perm));
                fi;
            od;
        od;
        Append(results, R_curr);
        R_curr := R_next;
        Print("  [elemab p=", p, " m=", m, " r=", r, "]",
              " size=", t + 1,
              " support orbits=", Length(R_curr), "\n");
    od;
    Append(results, R_curr);
    return results;
end;

# Enumerate rank-r orbit reps for [d=p^m, t]^k. Returns list of records:
#   rec(S, mults, p, m, r, k).
#
# Fast paths:
#   r = m*k: full rank.  Only size-k supports with direct-sum decomposition
#     contribute, and there is exactly one such orbit under GL_{m*k}(F_p)
#     wreath S_k.  Returns a single rep marked `full_T_k := true` which the
#     materializer handles specially (emit V = T^k itself).
ELEMAB_EnumerateRankRReps := function(p, m, k, r)
    local rec_data, all_subs, max_size, supports, S_data, results,
          mult_orbs, mt, rank;
    if r < m or r > m * k then return []; fi;
    if r = m * k then
        # Single direct-sum orbit.
        return [rec(p := p, m := m, k := k, r := r, full_T_k := true)];
    fi;
    rec_data := ELEMAB_GLrOnSubspaces(p, r, m);
    all_subs := rec_data.all_subs;
    max_size := Minimum(k, rec_data.n_subs);
    supports := ELEMAB_EnumerateSupports(p, m, r, max_size);
    results := [];
    for S_data in supports do
        if Length(S_data.S) = 0 then continue; fi;
        if Length(S_data.S) > k then continue; fi;
        # Full-rank constraint
        rank := ELEMAB_UnionRank(p, r, m, S_data.S, all_subs);
        if rank < r then continue; fi;
        mult_orbs := ELEMAB_MultOrbits(S_data.A_perm,
                                       Length(S_data.S), k);
        for mt in mult_orbs do
            Add(results, rec(S := S_data.S, mults := mt,
                             p := p, m := m, r := r, k := k));
        od;
    od;
    return results;
end;

# Total count for [d=p^m, t]^k across all r.
ELEMAB_CountAllReps := function(p, m, k)
    local total, r, n_r;
    total := 0;
    for r in [m..m * k] do
        n_r := Length(ELEMAB_EnumerateRankRReps(p, m, k, r));
        Print("  RANK r=", r, " reps=", n_r, "\n");
        total := total + n_r;
    od;
    return total;
end;

# ---------------------------------------------------------- materializer
# Build a basis (as r × m matrix over F_p) for the m-dim subspace whose
# encoded-nonzero set is W_set.
ELEMAB_BasisMatrix := function(p, r, m, W_set)
    local W, vecs;
    vecs := List(W_set, e -> ELEMAB_VecDecode(p, r, e));
    W := Subspace(GF(p)^r, vecs);
    # Basis(W) gives m vectors in F_p^r.  Stack as ROWS -> m × r matrix;
    # transpose -> r × m matrix whose columns are the basis of W.
    return TransposedMat(List(Basis(W), v -> ShallowCopy(v)));
end;

# Convert one rep (S, mults, r) to a permutation subgroup of S_{d*k}
# where T = TransitiveGroup(d, t) is elementary abelian (Z/p)^m and acts
# regularly on its d=p^m points.  gens_T is a list of m generators of T
# realizing the F_p^m -> T_orig isomorphism via basis (a_1,...,a_m) ->
# prod gens_T[i]^a_i.
ELEMAB_MaterializeRep := function(rep, d, T_orig, gens_T)
    local p, m, k, r, S, mults, rec_data, all_subs, Bs, idx, B, blocks,
          i, copy, gens, j, perm, v_block, t_elt, a, shift, g;
    p := rep.p; m := rep.m; k := rep.k; r := rep.r;
    if IsBound(rep.full_T_k) and rep.full_T_k then
        # V = T^k full subgroup; emit per-block generators of T.
        gens := [];
        for i in [1..k] do
            shift := MappingPermListList([1..d], [d*(i-1)+1..d*i]);
            for g in gens_T do
                Add(gens, g ^ shift);
            od;
        od;
        return gens;
    fi;
    S := rep.S; mults := rep.mults;
    rec_data := ELEMAB_GLrOnSubspaces(p, r, m);
    all_subs := rec_data.all_subs;
    # Build basis matrix for each support subspace.
    Bs := [];
    for idx in S do
        Add(Bs, ELEMAB_BasisMatrix(p, r, m, all_subs[idx]));
    od;
    # Block sequence with multiplicities.
    blocks := [];
    for i in [1..Length(S)] do
        for copy in [1..mults[i]] do
            Add(blocks, Bs[i]);   # each block is a r × m matrix
        od;
    od;
    # Now blocks[1..k] are the per-block r × m matrices.
    # For each row j of the implicit r × mk generator matrix, build a
    # permutation of d*k points.
    gens := [];
    for j in [1..r] do
        perm := ();
        for i in [1..k] do
            v_block := blocks[i][j];   # m-vector over F_p
            t_elt := One(T_orig);
            for a in [1..m] do
                t_elt := t_elt * gens_T[a] ^ IntFFE(v_block[a]);
            od;
            shift := MappingPermListList([1..d], [d*(i-1)+1..d*i]);
            perm := perm * (t_elt ^ shift);
        od;
        Add(gens, perm);
    od;
    return gens;
end;

# Standard combo-file emission, mirroring b21_writer_final.g.
ELEMAB_FormatGenList := function(gens)
    return Concatenation("[",
        JoinStringsWithSeparator(List(gens, g -> String(g)), ","),
        "]");
end;

# Materialize all reps and write to output_path.  d, t -> use
# TransitiveGroup(d, t) (must be elementary abelian of order p^m).
WriteBElemabFile := function(p, m, k, d, t, output_path)
    local T_orig, gens_T, all_reps, r, fout, t0, line, gens, total, rep,
          combo_pairs, cs_sum, cs_sizes, cs_rep, mk, gl_gens, M, ii, b_iter,
          WrG, V_basis, cs_d_factorial, fact_dk, rec_data, all_subs, Bs, idx,
          blocks, copy, j, M2, V_basis_mat, BasisFromRep;
    if d <> p^m then Error("d != p^m"); fi;
    T_orig := TransitiveGroup(d, t);
    gens_T := IndependentGeneratorsOfAbelianGroup(T_orig);
    if Length(gens_T) <> m then
        Error("|IndependentGenerators(T_orig)| != m");
    fi;
    t0 := Runtime();
    all_reps := [];
    for r in [m..m * k] do
        Print("r=", r, "...\n");
        Append(all_reps, ELEMAB_EnumerateRankRReps(p, m, k, r));
    od;
    total := Length(all_reps);
    Print("Total reps: ", total, "\n");

    # HARVEST: cs = (dk)! / (p^{mk} * |Stab_{(GL_m wr S_k)}(V)|) per rep.
    # |GL_m wr S_k| = |GL_m|^k * k!  is tiny (<= ~few thousand), so Stabilizer
    # call is essentially free.  Build the matrix group on F_p^{mk} once.
    mk := m * k;
    fact_dk := Factorial(d * k);
    gl_gens := [];
    for ii in [1..k] do
        for b_iter in GeneratorsOfGroup(GL(m, p)) do
            M2 := IdentityMat(mk) * One(GF(p));
            M2{[(ii-1)*m + 1 .. ii*m]}{[(ii-1)*m + 1 .. ii*m]} := b_iter;
            Add(gl_gens, M2);
        od;
    od;
    for ii in [1..k-1] do
        M2 := IdentityMat(mk) * One(GF(p));
        for j in [1..m] do
            M2[(ii-1)*m + j][(ii-1)*m + j] := Zero(GF(p));
            M2[ii*m + j][ii*m + j] := Zero(GF(p));
            M2[(ii-1)*m + j][ii*m + j] := One(GF(p));
            M2[ii*m + j][(ii-1)*m + j] := One(GF(p));
        od;
        Add(gl_gens, M2);
    od;
    WrG := Group(gl_gens);

    BasisFromRep := function(rep_in)
        local Bs2, blocks2, copy2, M3, j2;
        if IsBound(rep_in.full_T_k) and rep_in.full_T_k then
            return IdentityMat(mk) * One(GF(p));
        fi;
        rec_data := ELEMAB_GLrOnSubspaces(p, rep_in.r, m);
        all_subs := rec_data.all_subs;
        Bs2 := List(rep_in.S, idx ->
            ELEMAB_BasisMatrix(p, rep_in.r, m, all_subs[idx]));
        blocks2 := [];
        for ii in [1..Length(rep_in.S)] do
            for copy2 in [1..rep_in.mults[ii]] do Add(blocks2, Bs2[ii]); od;
        od;
        M3 := List([1..rep_in.r], j2 -> []);
        for ii in [1..k] do
            for j2 in [1..rep_in.r] do
                Append(M3[j2], blocks2[ii][j2]);
            od;
        od;
        return BasisVectors(SemiEchelonBasis(
            VectorSpace(GF(p), List(M3, row -> row * One(GF(p))))));
    end;

    cs_sum := 0;
    cs_sizes := [];
    for rep in all_reps do
        V_basis_mat := BasisFromRep(rep);
        cs_rep := fact_dk / (p^mk *
            Size(Stabilizer(WrG, V_basis_mat, OnSubspacesByCanonicalBasis)));
        cs_sum := cs_sum + cs_rep;
        Add(cs_sizes, cs_rep);
    od;

    fout := OutputTextFile(output_path, false);
    SetPrintFormattingStatus(fout, false);
    combo_pairs := List([1..k], i -> [d, t]);
    PrintTo(fout, "# combo: ", combo_pairs, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", Runtime() - t0, "\n");
    PrintTo(fout, "# class_sum: ", cs_sum, "\n");
    for rep in all_reps do
        gens := ELEMAB_MaterializeRep(rep, d, T_orig, gens_T);
        PrintTo(fout, ELEMAB_FormatGenList(gens), "\n");
    od;
    CloseStream(fout);
    Print("Wrote ", output_path, "  class_sum=", cs_sum, "\n");
    return total;
end;
