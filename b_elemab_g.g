################################################################################
# b_elemab_g.g
#
# Generalized ELEMAB: parameterized by a subgroup G <= GL_m(F_p) acting on
# each block by right-multiplication.  For G = GL_m(F_p), reduces to the
# original b_elemab.g (one marked-class per m-dim W).  For G ⊊ GL_m, each
# m-dim W has |GL_m|/|G| marked classes (G-orbits of ordered m-bases of W).
#
# Math: a subdirect V <= F_p^{mk} of dim r has a basis matrix
#   B = [B_1 | B_2 | ... | B_k]   (r x mk, each B_i r x m of rank m)
# The "marked class" of block i is the right-G-orbit of B_i's column tuple
# (m ordered vectors in F_p^r).
#
# Two V's are equivalent under G wr S_k iff their multisets of marked classes
# are equivalent under GL_r(F_p) x S_k.  GL_r acts on marked classes via
# left-multiplication on the column tuple; S_k permutes blocks.
#
# Algorithm: same support-first BFS as ELEMAB, but support elements are
# marked-class indices (not subspace indices).  GL_r acts on marked-class
# indices via the induced permutation.
################################################################################

# --- Encode an ordered m-tuple of F_p^r-vectors as a sorted list of ints ---
# Tuple is preserved as a LIST of ELEMAB-encoded integers (NOT a set, since
# order matters within a marked class).  Returns a copy.
ELEMAB_G_TupleEncode := function(p, r, m, tup)
    return List(tup, v -> ELEMAB_VecEncode(p, r, v));
end;

ELEMAB_G_TupleDecode := function(p, r, m, enc_list)
    return List(enc_list, e -> ELEMAB_VecDecode(p, r, e));
end;

# --- Right-multiply an m-tuple (cols of an r x m matrix) by g in GL_m ---
# tup is list of m r-vectors; g is m x m matrix.  Result: new tuple where
# new[i] = sum_j tup[j] * g[j][i].  Matrix view: tup as r x m matrix, post-
# mult by g, take columns again.
ELEMAB_G_RightMult := function(F, tup, g, m)
    local i, j, v;
    return List([1..m], i ->
        Sum([1..m], j -> tup[j] * g[j][i]));
end;

# --- Canonical (lex-min) encoding of an m-tuple under right-G action ---
ELEMAB_G_TupleCanon := function(F, tup, G_mats, p, r, m)
    local min_enc, g, image, image_enc;
    min_enc := ELEMAB_G_TupleEncode(p, r, m, tup);
    for g in G_mats do
        image := ELEMAB_G_RightMult(F, tup, g, m);
        image_enc := ELEMAB_G_TupleEncode(p, r, m, image);
        if image_enc < min_enc then min_enc := image_enc; fi;
    od;
    return min_enc;
end;

# --- Iterate ordered m-tuples of independent vectors in F_p^r ---
# Returns a list (size = |GL_m(F_p)| * #(m-dim subspaces of F_p^r)).
# For large r this can be expensive; use AllMarkedClasses (canon-iterated).
ELEMAB_G_AllIndependentTuples := function(p, r, m)
    local F, V_r, results, choose_next, build, n, basis_idx;
    F := GF(p);
    V_r := AsList(F^r);
    n := Length(V_r);   # = p^r
    results := [];
    # Iterate over m-tuples; check independence by computing rank.
    # For efficiency, build by extending one vec at a time, requiring each
    # extension to not lie in the span of previous picks.
    build := function(cur, span_dim)
        local v, new_cur, new_span;
        if Length(cur) = m then
            Add(results, ShallowCopy(cur));
            return;
        fi;
        for v in V_r do
            if IsZero(v) then continue; fi;
            new_cur := Concatenation(cur, [v]);
            # Check independence: rank of new_cur > rank of cur (rank=Length).
            if RankMat(new_cur * One(F)) > span_dim then
                build(new_cur, span_dim + 1);
            fi;
        od;
    end;
    build([], 0);
    return results;
end;

# --- Build all (G, r, m)-marked classes ---
# Each class is identified by its canonical (lex-min under right-G) encoding.
# Returns rec(
#   classes := sorted list of canonical encodings (each a list of m ints),
#   tuple_to_class := function(tup) -> class index (PositionSorted),
#   class_to_W_set := list mapping class idx to W (subspace) as sorted set
#                     of vector encodings (compatible with ELEMAB).
# )
ELEMAB_G_BuildMarkedClasses := function(p, r, m, G_mats)
    local F, tuples, classes, seen_dict, tup, canon, key, i, idx,
          class_to_W, span, e;
    F := GF(p);
    tuples := ELEMAB_G_AllIndependentTuples(p, r, m);
    classes := [];
    seen_dict := NewDictionary("", true);
    for tup in tuples do
        canon := ELEMAB_G_TupleCanon(F, tup, G_mats, p, r, m);
        if LookupDictionary(seen_dict, canon) = fail then
            AddDictionary(seen_dict, canon, Length(classes) + 1);
            Add(classes, canon);
        fi;
    od;
    # Sort canonical reps; renumber.
    SortBy(classes, c -> c);
    seen_dict := NewDictionary("", true);
    for i in [1..Length(classes)] do
        AddDictionary(seen_dict, classes[i], i);
    od;
    # W-set per class: the subspace spanned by the tuple's vectors, encoded
    # as sorted set of nonzero vector encodings (matches ELEMAB W-format).
    class_to_W := [];
    for canon in classes do
        tup := ELEMAB_G_TupleDecode(p, r, m, canon);
        span := Subspace(F^r, tup);
        Add(class_to_W, Set(List(Filtered(AsList(span), v -> not IsZero(v)),
            v -> ELEMAB_VecEncode(p, r, v))));
    od;
    return rec(
        classes := classes,
        seen_dict := seen_dict,
        class_to_W := class_to_W,
        p := p, r := r, m := m
    );
end;

# --- Action of g in GL_r on a class index ---
# Left-multiply each vector in tup by g, then re-canonicalize.
ELEMAB_G_GLrOnClassIdx := function(class_idx, g_left, mc_rec, G_mats)
    local F, p, r, m, canon, tup, new_tup, new_canon, lookup;
    p := mc_rec.p; r := mc_rec.r; m := mc_rec.m;
    F := GF(p);
    canon := mc_rec.classes[class_idx];
    tup := ELEMAB_G_TupleDecode(p, r, m, canon);
    new_tup := List(tup, v -> g_left * v);
    new_canon := ELEMAB_G_TupleCanon(F, new_tup, G_mats, p, r, m);
    lookup := LookupDictionary(mc_rec.seen_dict, new_canon);
    if lookup = fail then
        Error("GL_r action on class produced an invalid class");
    fi;
    return lookup;
end;

# --- Build GL_r(F_p) as a perm group on marked-class indices ---
ELEMAB_G_GLrOnClassesPerm := function(mc_rec, G_mats)
    local F, p, r, gl_r_mats, n_classes, gens_perm, g, perm_list, i;
    p := mc_rec.p; r := mc_rec.r;
    F := GF(p);
    gl_r_mats := GeneratorsOfGroup(GL(r, p));
    n_classes := Length(mc_rec.classes);
    gens_perm := List(gl_r_mats, g ->
        PermList(List([1..n_classes], i ->
            ELEMAB_G_GLrOnClassIdx(i, g, mc_rec, G_mats))));
    return Group(gens_perm, ());
end;

# --- Union-span (over F_p^r) of class indices ---
# = span of all vectors appearing in any class's tuple.
ELEMAB_G_UnionRank := function(S, mc_rec, p, r, m)
    local F, mat, idx, tup;
    F := GF(p);
    if Length(S) = 0 then return 0; fi;
    mat := [];
    for idx in S do
        tup := ELEMAB_G_TupleDecode(p, r, m, mc_rec.classes[idx]);
        Append(mat, tup);
    od;
    return RankMat(mat * One(F));
end;

# --- Cheap GL_r-invariant hash of a multiset of class indices ---
# Mirrors ELEMAB_SubsetHash but on marked classes.  Uses W-set per class for
# the rank-distribution + dual-hyperplane parts (cheap and effective).
ELEMAB_G_SubsetHash := function(S, mc_rec)
    local F, p, r, m, n, hash, k, sub, mat, idx, ranks, hyperplanes,
          counts_per_hp, H, count, tup, W_set, all_vecs;
    p := mc_rec.p; r := mc_rec.r; m := mc_rec.m;
    F := GF(p);
    n := Length(S);
    if n = 0 then return [0]; fi;
    hash := [n];
    # rank-distribution of sub-multisets (uses W-sets)
    for k in [1..n] do
        ranks := [];
        for sub in Combinations([1..n], k) do
            Add(ranks, ELEMAB_G_UnionRank(List(sub, i -> S[i]), mc_rec, p, r, m));
        od;
        Sort(ranks);
        Add(hash, ranks);
    od;
    # dual hyperplane histogram
    if r <= 8 then
        hyperplanes := AsList(Subspaces(F^r, r - 1));
        counts_per_hp := [];
        for H in hyperplanes do
            count := 0;
            for idx in S do
                W_set := mc_rec.class_to_W[idx];
                if ForAll(W_set, e -> ELEMAB_VecDecode(p, r, e) in H) then
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

# --- Stab in GL_r-on-classes of S, as perm on [1..|S|] ---
ELEMAB_G_StabAsPermOnSet := function(A, S, glr_on_classes_perm)
    local gens, g, perm_list, j, target_idx;
    if Length(S) = 0 then return SymmetricGroup(0); fi;
    if Size(A) = 1 then return Group((), ()); fi;
    gens := [];
    for g in GeneratorsOfGroup(A) do
        perm_list := [];
        for j in [1..Length(S)] do
            target_idx := S[j] ^ g;
            Add(perm_list, Position(S, target_idx));
        od;
        Add(gens, PermList(perm_list));
    od;
    return Group(gens, ());
end;

ELEMAB_G_MultOrbits := function(A_perm, n_S, k)
    local compositions, orbs;
    if k < n_S then return []; fi;
    compositions := OrderedPartitions(k, n_S);
    if Length(compositions) = 0 then return []; fi;
    orbs := OrbitsDomain(A_perm, compositions, Permuted);
    return List(orbs, o -> o[1]);
end;

# --- Support-first enumeration over marked classes ---
ELEMAB_G_EnumerateSupports := function(mc_rec, glr_on_classes, max_size, G_mats)
    local p, r, m, n_classes, R_curr, R_next, t, S_data, S, A, ext_orbs,
          orb, p_new, T, h, hash_keys, hash_buckets, bucket_idx, bucket,
          found, R_T, A_T, A_T_perm, results;
    p := mc_rec.p; r := mc_rec.r; m := mc_rec.m;
    n_classes := Length(mc_rec.classes);
    R_curr := [rec(S := [], A := glr_on_classes, A_perm := SymmetricGroup(0))];
    results := [];
    for t in [0..max_size - 1] do
        R_next := [];
        hash_keys := [];
        hash_buckets := [];
        for S_data in R_curr do
            S := S_data.S;
            A := S_data.A;
            ext_orbs := OrbitsDomain(A,
                Difference([1..n_classes], S), OnPoints);
            for orb in ext_orbs do
                p_new := orb[1];
                T := SortedList(Concatenation(S, [p_new]));
                h := ELEMAB_G_SubsetHash(T, mc_rec);
                bucket_idx := PositionSorted(hash_keys, h);
                if bucket_idx <= Length(hash_keys)
                    and hash_keys[bucket_idx] = h then
                    bucket := hash_buckets[bucket_idx];
                else
                    Add(hash_keys, h, bucket_idx);
                    Add(hash_buckets, [], bucket_idx);
                    bucket := hash_buckets[bucket_idx];
                fi;
                found := false;
                for R_T in bucket do
                    if RepresentativeAction(glr_on_classes, R_T.T, T, OnSets)
                        <> fail then
                        found := true; break;
                    fi;
                od;
                if not found then
                    Add(bucket, rec(T := T));
                    A_T := Stabilizer(glr_on_classes, T, OnSets);
                    A_T_perm := ELEMAB_G_StabAsPermOnSet(A_T, T,
                        glr_on_classes);
                    Add(R_next, rec(S := T, A := A_T, A_perm := A_T_perm));
                fi;
            od;
        od;
        Append(results, R_curr);
        R_curr := R_next;
        Print("  [elemab_g p=", p, " m=", m, " r=", r, "]",
              " size=", t + 1,
              " support orbits=", Length(R_curr), "\n");
    od;
    Append(results, R_curr);
    return results;
end;

# --- Enumerate (S, mults) rank-r orbit reps for [d, t]^k with G action ---
ELEMAB_G_EnumerateRankRReps := function(p, m, k, r, G_mats)
    local mc_rec, glr_on_classes, max_size, supports, S_data, results,
          mult_orbs, mt, rank;
    if r < m or r > m * k then return []; fi;
    # Build marked classes for (p, r, m, G).
    mc_rec := ELEMAB_G_BuildMarkedClasses(p, r, m, G_mats);
    if Length(mc_rec.classes) = 0 then return []; fi;
    glr_on_classes := ELEMAB_G_GLrOnClassesPerm(mc_rec, G_mats);
    max_size := Minimum(k, Length(mc_rec.classes));
    supports := ELEMAB_G_EnumerateSupports(mc_rec, glr_on_classes, max_size,
        G_mats);
    results := [];
    for S_data in supports do
        if Length(S_data.S) = 0 then continue; fi;
        if Length(S_data.S) > k then continue; fi;
        # Full-rank constraint: union of W's spans F_p^r.
        rank := ELEMAB_G_UnionRank(S_data.S, mc_rec, p, r, m);
        if rank < r then continue; fi;
        mult_orbs := ELEMAB_G_MultOrbits(S_data.A_perm,
            Length(S_data.S), k);
        for mt in mult_orbs do
            Add(results, rec(S := S_data.S, mults := mt,
                p := p, m := m, r := r, k := k,
                mc_rec := mc_rec));
        od;
    od;
    return results;
end;

ELEMAB_G_CountAllReps := function(p, m, k, G_mats)
    local total, r, n_r;
    total := 0;
    for r in [m..m * k] do
        n_r := Length(ELEMAB_G_EnumerateRankRReps(p, m, k, r, G_mats));
        Print("  RANK r=", r, " reps=", n_r, "\n");
        total := total + n_r;
    od;
    return total;
end;

# --- Build basis matrix for one block from its marked class ---
# Given class idx (referring to mc_rec.classes), returns r x m matrix whose
# columns are the canonical tuple.
ELEMAB_G_BasisMatrix := function(class_idx, mc_rec)
    local p, r, m, tup, i, j, mat;
    p := mc_rec.p; r := mc_rec.r; m := mc_rec.m;
    tup := ELEMAB_G_TupleDecode(p, r, m, mc_rec.classes[class_idx]);
    # tup is m vectors of length r.  Return r x m matrix (columns = tup).
    mat := List([1..r], i -> ListWithIdenticalEntries(m, Zero(GF(p))));
    for i in [1..r] do
        for j in [1..m] do
            mat[i][j] := tup[j][i];
        od;
    od;
    return mat;
end;
