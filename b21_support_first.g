################################################################################
# b21_support_first.g
#
# Support-first enumeration of nondegenerate [k, r]_2 binary linear codes
# (= GL_r-orbits on size-k multisets of nonzero vectors of F_2^r) via
# stabilizer-orbit support extension.
#
# Key idea (per user spec):
#
#   R[0] := { empty support }
#   for t = 0..k-1:
#       R[t+1] := empty
#       for each support rep S in R[t]:
#           A := Stab_{GL_r}(S)
#           for each A-orbit O on F_2^r \ {0} \ S:
#               pick p in O
#               T := S union {p}
#               if T not yet seen up to GL_r:
#                   add T to R[t+1] (with its Stab)
#
# Then for each support S of size s, enumerate multiplicity assignments
# (positive integers summing to k) modulo Aut(S) (= the stabilizer's action
# on S as a permutation group).
################################################################################

LoadPackage("guava", false);

# Permutation-equivalence test for two subsets viewed as columns of binary codes.
IsEquivalentSubsetCode := function(S1, S2, r)
    local m1, m2, c1, c2;
    if Length(S1) <> Length(S2) then return false; fi;
    m1 := TransposedMat(List(S1, e -> DecodingOf(e, r)));
    m2 := TransposedMat(List(S2, e -> DecodingOf(e, r)));
    c1 := GeneratorMatCode(m1, GF(2));
    c2 := GeneratorMatCode(m2, GF(2));
    return IsEquivalent(c1, c2);
end;

# Parity of popcount(a AND b) for non-negative integers (up to r bits).
BitAndPopcountMod2 := function(a, b, r)
    local p, i;
    p := 0;
    for i in [0..r-1] do
        if ((QuoInt(a, 2^i) mod 2) = 1) and ((QuoInt(b, 2^i) mod 2) = 1) then
            p := 1 - p;
        fi;
    od;
    return p;
end;

# Cache GL_r as permutation group on encodings of F_2^r \ {0}.
# Permutation-group stabilizer / orbit are much faster than matrix-group ones.
GLR_PERM_CACHE := rec();
GetGLrAsPermGroup := function(r)
    local key, n, V, gens, perms;
    key := String(r);
    if IsBound(GLR_PERM_CACHE.(key)) then return GLR_PERM_CACHE.(key); fi;
    n := 2^r - 1;
    V := List([1..n], e -> DecodingOf(e, r));
    gens := GeneratorsOfGroup(GL(r, 2));
    perms := List(gens, g -> PermList(List([1..n], i -> EncodingOf(V[i] * g))));
    GLR_PERM_CACHE.(key) := Group(perms);
    return GLR_PERM_CACHE.(key);
end;

# Stabilizer of subset S (set of encodings) in GL_r-as-perm-group.
StabGLrOfSet := function(S, r)
    return Stabilizer(GetGLrAsPermGroup(r), Set(S), OnSets);
end;

# A-orbits on encodings (A is permutation subgroup of GL_r-perm-group).
ComputeAEncodingOrbits := function(A, encodings, r)
    return OrbitsDomain(A, encodings, OnPoints);
end;

# Apply g (permutation) to encoding e.
ApplyGLrEncoding := function(g, e, r)
    return e ^ g;
end;

# Canonical key for a subset S under GL_r action: lex-min over GL_r-as-perm-group.
# Uses GAP's permutation-group iteration (= internally orbit-stabilizer chain).
CanonicalSubsetKey := function(S, r)
    local G, best, g, image, sorted;
    G := GetGLrAsPermGroup(r);
    best := fail;
    for g in G do
        image := SortedList(OnTuples(S, g));
        if best = fail or image < best then best := image; fi;
    od;
    return best;
end;

# Set-Stabilizer orbit-based canonical: instead of iterating all of GL_r, use
# orbit traversal. For each S, compute SmallestImage if available.
# Fallback: brute force.

# All A-orbits on multiplicity assignments to S (as ordered tuple of |S| values),
# where each value is a positive integer and the sum is total. A acts via its
# permutation action on indices of S.
# Returns list of representative tuples (one per A-orbit).
MultiplicityOrbitsOnSetByAut := function(A_perm, S_size, total)
    local n, compositions, c, orbs, ms;
    n := S_size;
    # Compositions of total into n positive parts
    compositions := [];
    # Iterative: stars-and-bars via partition
    if total < n then return []; fi;
    # Generate via recursive helper
    compositions := Filtered(OrderedPartitions(total, n), c -> ForAll(c, x -> x >= 1));
    if Length(compositions) = 0 then return []; fi;
    # A_perm acts on [1..n] by permutation; this induces action on tuples by
    # position-permutation: g * (c_1,...,c_n) = (c_{g^{-1}(1)}, ..., c_{g^{-1}(n)}).
    orbs := OrbitsDomain(A_perm, compositions, Permuted);
    return List(orbs, o -> o[1]);
end;

# Compute permutation action of stabilizer A on the support set S.
# Returns A_perm as a subgroup of Sym([1..|S|]).
StabPermutationOnSet := function(A, S, r)
    local n, gens_perm, g, perm_list, j, target_e, target_pos;
    n := Length(S);
    if n = 0 then return SymmetricGroup(0); fi;
    if Size(A) = 1 then return Group(()); fi;
    gens_perm := [];
    for g in GeneratorsOfGroup(A) do
        perm_list := [];
        for j in [1..n] do
            target_e := S[j] ^ g;
            target_pos := Position(S, target_e);
            if target_pos = fail then
                Error("Stab does not preserve set! g=", g, " S=", S);
            fi;
            Add(perm_list, target_pos);
        od;
        Add(gens_perm, PermList(perm_list));
    od;
    return Group(gens_perm, ());
end;

# Cheap GL_r-invariant hash of a subset S of F_2^r vectors.
# Combines:
#  1. Rank distribution of subsets of S (matroid-level invariant).
#  2. Weight enumerator of the binary code with columns = S (GL_r x S_s-invariant).
SubsetCheapHash := function(S, r)
    local n, hash, k, count_by_rank, sub, rank, mat,
          a_int, a_vec, weights, cnt, b_int, e;
    n := Length(S);
    if n = 0 then return [0]; fi;
    hash := [n];
    # Rank distribution
    for k in [1..n] do
        count_by_rank := ListWithIdenticalEntries(r + 1, 0);
        for sub in Combinations(S, k) do
            mat := List(sub, e -> DecodingOf(e, r)) * One(GF(2));
            rank := RankMat(mat);
            count_by_rank[rank + 1] := count_by_rank[rank + 1] + 1;
        od;
        Add(hash, count_by_rank);
    od;
    # Weight enumerator of code: for each a in F_2^r \ {0}, count elements of S
    # whose inner product with a is 1. Sort the resulting list of weights.
    weights := [];
    for a_int in [1..2^r - 1] do
        cnt := 0;
        for e in S do
            if BitAndPopcountMod2(a_int, e, r) = 1 then cnt := cnt + 1; fi;
        od;
        Add(weights, cnt);
    od;
    Sort(weights);
    Add(hash, weights);
    return hash;
end;

# Enumerate support-orbit reps via dedup at each level.
# Primary filter: cheap rank-distribution hash.
# Collision resolution: brute-force GL_r CanonicalSubsetKey.
EnumerateSupports := function(r, max_size)
    local n, U, R_curr, R_next, t, S_data, S, A, ext_orbs, orb, p, T,
          h, hash_keys, hash_buckets, bucket_idx, bucket, found, R_T,
          A_T, A_T_perm, results;
    n := 2^r - 1;
    U := [1..n];
    R_curr := [rec(S := [], A := GetGLrAsPermGroup(r),
                   A_perm := SymmetricGroup(0))];
    results := [];
    for t in [0..max_size - 1] do
        R_next := [];
        # hash_keys parallel to hash_buckets: hash_keys[i] = i-th cheap hash,
        # hash_buckets[i] = list of {T, ...} entries with that hash.
        hash_keys := [];
        hash_buckets := [];
        for S_data in R_curr do
            S := S_data.S;
            A := S_data.A;
            ext_orbs := ComputeAEncodingOrbits(A, Difference(U, S), r);
            for orb in ext_orbs do
                p := orb[1];
                T := SortedList(Concatenation(S, [p]));
                h := SubsetCheapHash(T, r);
                bucket_idx := PositionSorted(hash_keys, h);
                if bucket_idx <= Length(hash_keys) and hash_keys[bucket_idx] = h then
                    bucket := hash_buckets[bucket_idx];
                else
                    Add(hash_keys, h, bucket_idx);
                    Add(hash_buckets, [], bucket_idx);
                    bucket := hash_buckets[bucket_idx];
                fi;
                # Hash collision: use GUAVA IsEquivalent to compare codes.
                found := false;
                for R_T in bucket do
                    if IsEquivalentSubsetCode(R_T.T, T, r) then
                        found := true; break;
                    fi;
                od;
                if not found then
                    Add(bucket, rec(T := T));
                    A_T := StabGLrOfSet(T, r);
                    A_T_perm := StabPermutationOnSet(A_T, T, r);
                    Add(R_next, rec(S := T, A := A_T, A_perm := A_T_perm));
                fi;
            od;
        od;
        Append(results, R_curr);
        R_curr := R_next;
        Print("  size=", t + 1, " support orbits=", Length(R_curr), "\n");
    od;
    Append(results, R_curr);
    return results;
end;

# Enumerate orbit reps for rank r and length k=10.
# For each support S of size s, count Aut(S)-orbits on multiplicity assignments
# (= positive integers summing to k).
# Returns list of records: rec(S, mult_tuple) where mult_tuple gives multiplicities
# assigned to elements of S in order.
EnumerateRankRReps_SupportFirst := function(r, k)
    local supports, S_data, results, mult_orbs, mt, max_size, rank;
    max_size := Minimum(k, 2^r - 1);
    supports := EnumerateSupports(r, max_size);
    results := [];
    for S_data in supports do
        if Length(S_data.S) = 0 then continue; fi;
        if Length(S_data.S) > k then continue; fi;
        # Filter: support must have RANK r in F_2^r (= span F_2^r).
        rank := RankMat(List(S_data.S, e -> DecodingOf(e, r)) * One(GF(2)));
        if rank < r then continue; fi;
        # Multiplicity orbits: positive parts summing to k, mod A_perm.
        mult_orbs := MultiplicityOrbitsOnSetByAut(
            S_data.A_perm, Length(S_data.S), k);
        for mt in mult_orbs do
            Add(results, rec(S := S_data.S, mults := mt, r := r));
        od;
    od;
    return results;
end;
