###############################################################################
#
# lifting_method_fast_v2.g - Chief Series Lifting + Normalizer deduplication
#
# Key insights:
# 1. Use chief series lifting to avoid full subgroup enumeration
# 2. Use normalizer of Young subgroup for final deduplication (fast)
# 3. Use invariant bucketing to reduce comparisons
#
# This version replaces ConjugacyClassesSubgroups(P) with the lifting algorithm
# from lifting_algorithm.g to enable computation of S14 and beyond.
#
###############################################################################

# Load the lifting algorithm
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# Load the H^1 orbital complement enumeration (Phase 2 optimization)
# This provides GetH1OrbitRepresentatives which uses normalizer orbit
# computation on H^1 to dramatically reduce complement enumeration time.
if IsReadableFile("C:/Users/jeffr/Downloads/Lifting/h1_action.g") then
    Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");
fi;

# Safety check: refuse to run with a memory limit.
# GAP's default -o limit causes silent truncation of heavy computations,
# producing partial results that appear complete. Always use -o 0.
if GasmanLimits().max <> 0 then
    Error("FATAL: GAP is running with a memory limit (",
          GasmanLimits().max, " bytes). ",
          "Use -o 0 to allow unlimited memory. ",
          "Without this, heavy computations silently produce partial results.");
fi;

# Try to load the 'images' package for canonical form deduplication
IMAGES_AVAILABLE := false;
if not (IsBound(SKIP_IMAGES_LOAD) and SKIP_IMAGES_LOAD = true) then
    if TestPackageAvailability("images") <> fail then
        if LoadPackage("images", false) then
            IMAGES_AVAILABLE := true;
            Print("images package loaded - canonical dedup enabled.\n");
        fi;
    fi;
fi;

LIFT_LOG := "C:/Users/jeffr/Downloads/Lifting/lift_fast2_log.txt";

# Cache for n-values
LIFT_CACHE := rec();

# Cache for FPF subdirect computations, keyed by sorted transitive group IDs
FPF_SUBDIRECT_CACHE := rec();

# Load the precomputed database for persistent caching
# This must be done AFTER the caches (LIFT_CACHE, FPF_SUBDIRECT_CACHE) are defined
# Set SKIP_DATABASE_LOAD := true before Read() to skip (e.g., invariant-only workers)
if not (IsBound(SKIP_DATABASE_LOAD) and SKIP_DATABASE_LOAD = true) then
    if IsReadableFile("C:/Users/jeffr/Downloads/Lifting/database/load_database.g") then
        Read("C:/Users/jeffr/Downloads/Lifting/database/load_database.g");
        LoadDatabaseIfExists();
    fi;
fi;

# ComputeCacheKey(transFactors)
# Compute a cache key from a list of transitive groups
# Key = sorted list of (degree, TransitiveIdentification) pairs
ComputeCacheKey := function(transFactors)
    local keyList, T, deg, id;

    keyList := [];
    for T in transFactors do
        deg := NrMovedPoints(T);
        id := TransitiveIdentification(T);
        Add(keyList, [deg, id]);
    od;
    Sort(keyList);

    return String(keyList);
end;

LogMsg := function(msg)
    AppendTo(LIFT_LOG, msg, "\n");
end;

InitLog := function(n)
    PrintTo(LIFT_LOG, "Lifting Fast V2 for S_", n, "\n");
    AppendTo(LIFT_LOG, "Started: ", StringTime(Runtime()), "\n");
    AppendTo(LIFT_LOG, RepeatedString("=", 60), "\n\n");
end;

###############################################################################
# Partition Utilities
###############################################################################

PartitionsMinPart := function(n, minpart)
    local result, helper;

    helper := function(remaining, maxpart, current)
        local i;
        if remaining = 0 then
            Add(result, ShallowCopy(current));
            return;
        fi;
        for i in [Minimum(remaining, maxpart), Minimum(remaining, maxpart)-1 .. minpart] do
            Add(current, i);
            helper(remaining - i, i, current);
            Remove(current);
        od;
    end;

    result := [];
    helper(n, n, []);
    return result;
end;

###############################################################################
# Build Young Subgroup Normalizer
###############################################################################

BuildYoungNormalizer := function(n, partition)
    local Sn, gens, offset, d, i;

    Sn := SymmetricGroup(n);

    # Build Young subgroup S_{d1} x S_{d2} x ... x S_{dk}
    gens := [];
    offset := 0;
    for d in partition do
        if d >= 2 then
            Add(gens, (offset+1, offset+2));
            if d >= 3 then
                Add(gens, PermList(Concatenation(
                    [1..offset],
                    [offset+2..offset+d],
                    [offset+1],
                    [offset+d+1..n]
                )));
            fi;
        fi;
        offset := offset + d;
    od;

    if Length(gens) = 0 then
        return Sn;
    fi;

    return Normalizer(Sn, Group(gens));
end;

###############################################################################
# Phase 4: Wreath Product Conjugacy Testing
#
# For partitions with repeated parts [d,d,...,d] (k copies), use S_d ≀ S_k
# structure for more efficient conjugacy testing.
###############################################################################

# CountRepeatedParts(partition)
# Returns a list of [value, count] pairs for parts that repeat
CountRepeatedParts := function(partition)
    local counts, result, d, lastVal, lastCount;

    if Length(partition) = 0 then
        return [];
    fi;

    result := [];
    lastVal := partition[1];
    lastCount := 1;

    for d in partition{[2..Length(partition)]} do
        if d = lastVal then
            lastCount := lastCount + 1;
        else
            if lastCount > 1 then
                Add(result, [lastVal, lastCount]);
            fi;
            lastVal := d;
            lastCount := 1;
        fi;
    od;

    if lastCount > 1 then
        Add(result, [lastVal, lastCount]);
    fi;

    return result;
end;

# BuildPerComboNormalizer(partition, currentFactors, n)
# Build a tight normalizer for a specific factor combination.
# For each block k, use N_{S_{d_k}}(T_k) instead of the full S_{d_k}.
# Add block-swap generators for positions with same (degree, TI).
BuildPerComboNormalizer := function(partition, currentFactors, n)
    local gens, offset, k, d, shiftedT, normT, groupsByDegTI,
          key, positions, m, p, q, offset_p, offset_q, mapping, i, perm;

    gens := [];
    offset := 0;

    # Per-block normalizers N_{S_{d_k}}(T_k)
    for k in [1..Length(partition)] do
        d := partition[k];
        shiftedT := ShiftGroup(currentFactors[k], offset);
        normT := Normalizer(SymmetricGroup([offset+1..offset+d]), shiftedT);
        Append(gens, GeneratorsOfGroup(normT));
        offset := offset + d;
    od;

    # Block swaps for positions with same (degree, TransitiveIdentification)
    groupsByDegTI := rec();
    for k in [1..Length(currentFactors)] do
        key := Concatenation(String(partition[k]), "_",
               String(TransitiveIdentification(currentFactors[k])));
        if not IsBound(groupsByDegTI.(key)) then
            groupsByDegTI.(key) := [];
        fi;
        Add(groupsByDegTI.(key), k);
    od;

    for key in RecNames(groupsByDegTI) do
        positions := groupsByDegTI.(key);
        if Length(positions) >= 2 then
            d := partition[positions[1]];
            # Adjacent transpositions generate S_m on these blocks
            for m in [1..Length(positions)-1] do
                p := positions[m];
                q := positions[m+1];
                offset_p := Sum(partition{[1..p-1]});
                offset_q := Sum(partition{[1..q-1]});
                mapping := [1..n];
                for i in [1..d] do
                    mapping[offset_p + i] := offset_q + i;
                    mapping[offset_q + i] := offset_p + i;
                od;
                perm := PermList(mapping);
                Add(gens, perm);
            od;
        fi;
    od;

    if Length(gens) = 0 then
        return Group(());
    fi;

    return Group(gens);
end;

# BuildConjugacyTestGroup(n, partition)
# Build the appropriate group for conjugacy testing based on partition structure.
# Uses wreath product structure when partition has repeated parts.
BuildConjugacyTestGroup := function(n, partition)
    local Sn, repeated, gens, offset, d, i, bestRep, maxReps, blockSize,
          numBlocks, blockOffset, permGens, j, blockPerm, mapping;

    Sn := SymmetricGroup(n);
    repeated := CountRepeatedParts(partition);

    # If no significant repetition, fall back to Young normalizer
    if Length(repeated) = 0 then
        return BuildYoungNormalizer(n, partition);
    fi;

    # Find the largest repeated block
    maxReps := 0;
    bestRep := fail;
    for d in repeated do
        if d[2] > maxReps then
            maxReps := d[2];
            bestRep := d;
        fi;
    od;

    # Only use wreath product if we have at least 3 repetitions
    if maxReps < 3 then
        return BuildYoungNormalizer(n, partition);
    fi;

    blockSize := bestRep[1];
    numBlocks := bestRep[2];

    # Build generators for wreath product S_d ≀ S_k
    # This includes:
    # 1. S_d acting on each block (from Young subgroup)
    # 2. S_k permuting the blocks

    gens := [];

    # First, find where the repeated blocks start
    blockOffset := 0;
    for d in partition do
        if d = blockSize then
            break;
        fi;
        blockOffset := blockOffset + d;
    od;

    # Add S_d generators for each block
    for i in [0..numBlocks-1] do
        offset := blockOffset + i * blockSize;
        if blockSize >= 2 then
            Add(gens, (offset+1, offset+2));
            if blockSize >= 3 then
                Add(gens, PermList(Concatenation(
                    [1..offset],
                    [offset+2..offset+blockSize],
                    [offset+1],
                    [offset+blockSize+1..n]
                )));
            fi;
        fi;
    od;

    # Add S_k generators (block permutations)
    # Transposition swapping first two blocks
    if numBlocks >= 2 then
        mapping := [1..n];
        for j in [1..blockSize] do
            # Swap positions in first and second blocks
            mapping[blockOffset + j] := blockOffset + blockSize + j;
            mapping[blockOffset + blockSize + j] := blockOffset + j;
        od;
        blockPerm := PermList(mapping);
        if blockPerm <> () then
            Add(gens, blockPerm);
        fi;
    fi;

    # Cycle through all blocks (for k >= 3)
    if numBlocks >= 3 then
        mapping := [1..n];
        for i in [0..numBlocks-2] do
            for j in [1..blockSize] do
                mapping[blockOffset + i * blockSize + j] :=
                    blockOffset + (i + 1) * blockSize + j;
            od;
        od;
        for j in [1..blockSize] do
            mapping[blockOffset + (numBlocks - 1) * blockSize + j] :=
                blockOffset + j;
        od;
        blockPerm := PermList(mapping);
        if blockPerm <> () then
            Add(gens, blockPerm);
        fi;
    fi;

    if Length(gens) = 0 then
        return Sn;
    fi;

    # Return normalizer of the wreath-structured group
    return Normalizer(Sn, Group(gens));
end;

###############################################################################
# Shift groups
###############################################################################

ShiftGroup := function(G, offset)
    local moved, gens, newGens, g, newPerm, i, img;

    if offset = 0 then
        return G;
    fi;

    moved := MovedPoints(G);
    if Length(moved) = 0 then
        return Group(());
    fi;

    gens := GeneratorsOfGroup(G);
    newGens := [];

    for g in gens do
        newPerm := [];
        for i in moved do
            img := i^g;
            Add(newPerm, [i + offset, img + offset]);
        od;
        Add(newGens, MappingPermListList(
            List(newPerm, x -> x[1]),
            List(newPerm, x -> x[2])
        ));
    od;

    if Length(newGens) = 0 then
        return Group(());
    fi;

    return Group(newGens);
end;

###############################################################################
# Phase 2: Specialized handling for n₁=2 partitions (Holt's fiber product)
###############################################################################

# EnumerateSubdirectSubspaces(k)
# Enumerate conjugacy class representatives of subdirect subgroups of (C_2)^k
# using GF(2) linear algebra. Returns list of generator matrices.
EnumerateSubdirectSubspaces := function(k)
    local subspaces, d, pivots, nonPivotCols, freePositions,
          nFree, assignment, matrix, isSubdirect, c, i, temp, one,
          orbitReps, seen, canonical, key, sp;

    if k = 1 then
        # Only subdirect is the full group
        return [IdentityMat(1, GF(2))];
    fi;

    one := One(GF(2));
    subspaces := [];

    # RREF enumeration: directly construct every d-dimensional subspace
    # of GF(2)^k via its unique reduced row echelon form.
    # Each RREF matrix has pivot columns (with a single 1) and free entries
    # in non-pivot columns after the pivot. This visits exactly one candidate
    # per actual subspace, avoiding the exponential Combinations search.

    for d in [1..k] do
        if d = k then
            # Full space is always subdirect
            Add(subspaces, IdentityMat(k, GF(2)));
            continue;
        fi;

        for pivots in Combinations([1..k], d) do
            nonPivotCols := Difference([1..k], pivots);

            # Prune: if any non-pivot column is before all pivots,
            # it will always be zero -> not subdirect
            if nonPivotCols[1] < pivots[1] then
                continue;
            fi;

            # Compute free entry positions: (row, col) pairs
            # Row i has free entries at non-pivot columns > pivots[i]
            freePositions := [];
            for i in [1..d] do
                for c in nonPivotCols do
                    if c > pivots[i] then
                        Add(freePositions, [i, c]);
                    fi;
                od;
            od;
            nFree := Length(freePositions);

            # Iterate over all 2^nFree binary assignments of free entries
            for assignment in [0..2^nFree - 1] do
                # Build the RREF matrix
                matrix := NullMat(d, k, GF(2));
                for i in [1..d] do
                    matrix[i][pivots[i]] := one;
                od;
                temp := assignment;
                for i in [1..nFree] do
                    if IsOddInt(temp) then
                        matrix[freePositions[i][1]][freePositions[i][2]] := one;
                    fi;
                    temp := QuoInt(temp, 2);
                od;

                # Check subdirectness: every non-pivot column must have
                # at least one nonzero entry (pivot columns are guaranteed)
                isSubdirect := true;
                for c in nonPivotCols do
                    if ForAll([1..d], i -> IsZero(matrix[i][c])) then
                        isSubdirect := false;
                        break;
                    fi;
                od;

                if isSubdirect then
                    Add(subspaces, List(matrix, row -> List(row)));
                fi;
            od;
        od;
    od;

    # OPTIMIZATION: Deduplicate under S_k symmetry (all k C2 factors are identical)
    if k > 1 then
        orbitReps := [];
        seen := rec();
        for sp in subspaces do
            canonical := CanonicalSubspaceUnderSk(sp, 0, k);
            key := String(canonical);
            if not IsBound(seen.(key)) then
                seen.(key) := true;
                Add(orbitReps, sp);
            fi;
        od;
        return orbitReps;
    fi;

    return subspaces;
end;

###############################################################################
# C2 Fiber Product Optimization - Complete Rewrite
#
# For T × C2^k, subdirects come from:
# 1. Hom(T, C2) = Hom(T/T', C2) gives a vector space V over GF(2) of dimension r
# 2. Subdirects of T × C2^k correspond to subdirects of C2^r × C2^k via
#    the map (φ₁,...,φᵣ, id,...,id) where φᵢ are independent quotient maps
# 3. We enumerate subdirect subspaces W ≤ GF(2)^(r+k) and lift back
###############################################################################

# GetQuotientMapsToC2(G)
# Returns a list of index-2 subgroups (kernels of quotient maps G → C2)
# and the dimension r = |Hom(G, C2)| - 1 (excluding trivial hom)
GetQuotientMapsToC2 := function(G)
    local D, hom, abelianization, idx2subs, H, r, independentKernels,
          currentInter, K, newInter;

    # G/G' is the abelianization; Hom(G, C2) = Hom(G/G', C2)
    D := DerivedSubgroup(G);

    if Index(G, D) < 2 then
        # G = G', so G is perfect, no quotients to C2
        return rec(kernels := [], dimension := 0);
    fi;

    hom := SafeNaturalHomByNSG(G, D);
    if hom = fail then
        return rec(kernels := [], dimension := 0);
    fi;
    abelianization := ImagesSource(hom);

    # Dimension r = number of even entries in AbelianInvariants
    # For each C_{n_i} factor, Hom(C_{n_i}, C2) is C2 if n_i is even, trivial otherwise
    r := Number(AbelianInvariants(abelianization), x -> x mod 2 = 0);

    if r = 0 then
        return rec(kernels := [], dimension := 0);
    fi;

    # Collect ALL index-2 subgroups (kernels of quotient maps G → C2)
    idx2subs := [];
    for H in MaximalSubgroups(abelianization) do
        if Index(abelianization, H) = 2 then
            Add(idx2subs, PreImages(hom, H));
        fi;
    od;

    # Select exactly r INDEPENDENT kernels (a basis of Hom(G, C2))
    # For C2^r, there are 2^r - 1 hyperplanes but only r are needed.
    # Independence: each new kernel must strictly shrink the intersection.
    independentKernels := [];
    currentInter := G;
    for K in idx2subs do
        newInter := Intersection(currentInter, K);
        if Size(newInter) < Size(currentInter) then
            Add(independentKernels, K);
            currentInter := newInter;
            if Length(independentKernels) = r then
                break;
            fi;
        fi;
    od;

    return rec(kernels := independentKernels, dimension := r);
end;

# HasSmallAbelianization(G)
# Returns true if dim(Hom(G, C2)) ≤ 1, meaning C2 optimization is efficient
# Groups with r > 1 (like V4 with r=2, D8 with r=3) cause duplicate enumeration
HasSmallAbelianization := function(G)
    local D, hom, abelianization, idx2count, H;

    D := DerivedSubgroup(G);

    # Perfect group: r = 0
    if Size(G) = Size(D) then
        return true;
    fi;

    # Count index-2 subgroups
    hom := SafeNaturalHomByNSG(G, D);
    if hom = fail then
        return true;  # Can't compute; assume small abelianization (safe fallback)
    fi;
    abelianization := ImagesSource(hom);

    idx2count := 0;
    for H in MaximalSubgroups(abelianization) do
        if Index(abelianization, H) = 2 then
            idx2count := idx2count + 1;
            if idx2count > 1 then
                return false;  # r > 1, don't use C2 opt
            fi;
        fi;
    od;

    return true;  # r ≤ 1
end;

# BuildSubdirectFromSubspace(T, kernels, c2Subspace, shifted, offsets, numC2, nonC2Start)
# Given:
#   - T: the non-C2 factor
#   - kernels: list of index-2 subgroups of T (kernels of quotient maps φᵢ)
#   - c2Subspace: a subspace W ≤ GF(2)^(r+k) encoded as list of basis vectors
#   - The first r coordinates correspond to quotient maps φᵢ
#   - The last k coordinates correspond to C2 factors
# Returns: the subdirect product group
BuildSubdirectFromSubspace := function(T, kernels, c2Subspace, shifted, offsets, numC2, nonC2Start)
    local gens, r, k, g, vec, c2Component, i, perm, off, row,
          basisMat, firstRcols, coeffs, c2cols;

    r := Length(kernels);
    k := numC2;
    gens := [];

    # Precompute: extract first-r and last-k columns of the basis as GF(2) matrices
    # Normalize to GF(2) elements to handle mixed integer/GF(2) inputs
    basisMat := List(c2Subspace, function(row)
        local j, v;
        v := [];
        for j in [1..Length(row)] do
            if IsOne(row[j]) or row[j] = 1 then
                Add(v, One(GF(2)));
            else
                Add(v, Zero(GF(2)));
            fi;
        od;
        return v;
    end);
    firstRcols := List(basisMat, row -> row{[1..r]});
    c2cols := List(basisMat, row -> row{[r+1..r+k]});

    # For each generator of T, compute its image under all quotient maps
    for g in GeneratorsOfGroup(T) do
        # Compute which quotient maps send g to 1 ∈ C2 (i.e., g ∉ kernel)
        vec := [];
        for i in [1..r] do
            if g in kernels[i] then
                Add(vec, Zero(GF(2)));
            else
                Add(vec, One(GF(2)));
            fi;
        od;

        # Solve the linear system: find coefficients a such that
        # Σ a_i * firstRcols[i] = vec over GF(2)
        # Then c2Component = Σ a_i * c2cols[i]
        coeffs := SolutionMat(firstRcols, vec);

        if coeffs <> fail then
            # Compute c2 component from the solution
            c2Component := ListWithIdenticalEntries(k, Zero(GF(2)));
            for i in [1..Length(c2Subspace)] do
                if IsOne(coeffs[i]) then
                    for j in [1..k] do
                        c2Component[j] := c2Component[j] + c2cols[i][j];
                    od;
                fi;
            od;
        else
            # vec not in row space of first r columns -> g not in S_W
            # Use zero c2 component (will be filtered by IsFPFSubdirect later)
            c2Component := ListWithIdenticalEntries(k, Zero(GF(2)));
        fi;

        # Build permutation for C2^k component
        perm := ();
        for i in [1..k] do
            if IsOne(c2Component[i]) or c2Component[i] = 1 then
                off := offsets[nonC2Start + i];
                perm := perm * (off + 1, off + 2);
            fi;
        od;

        Add(gens, g * perm);
    od;

    # Also add generators for the C2^k part that are independent of T
    # These are elements (0, c) ∈ W (where 0 is the zero vector in C2^r)
    for row in c2Subspace do
        if ForAll([1..r], i -> IsZero(row[i]) or row[i] = 0) then
            # This row has zero in the T-quotient part
            perm := ();
            for i in [1..k] do
                if IsOne(row[r + i]) or row[r + i] = 1 then
                    off := offsets[nonC2Start + i];
                    perm := perm * (off + 1, off + 2);
                fi;
            od;
            if perm <> () then
                Add(gens, perm);
            fi;
        fi;
    od;

    gens := Filtered(gens, x -> x <> ());
    if Length(gens) = 0 then
        return Group(());
    fi;

    return Group(gens);
end;

# CanonicalSubspaceUnderSk(subspace, r, k)
# Compute canonical form of subspace under S_k action on last k coordinates.
# S_k permutes coordinates r+1, r+2, ..., r+k.
# Returns a canonical representative (sorted lexicographically).
CanonicalSubspaceUnderSk := function(subspace, r, k)
    local n, perm, permutedBasis, v, newV, i, j, canonical, p,
          colWeights, sortedCols, colPerm, mat, d, bestPerm,
          candidates, newCandidates, col, bestCol, weight;

    if k <= 1 then
        return subspace;  # No symmetry to exploit
    fi;

    n := r + k;

    if k <= 5 then
        # For small k (k! <= 120), brute force is fine
        canonical := List(subspace, v -> List(v));
        Sort(canonical);

        for p in SymmetricGroup(k) do
            perm := Concatenation([1..r], List([1..k], i -> r + i^p));
            permutedBasis := [];
            for v in subspace do
                newV := List([1..n], i -> v[perm[i]]);
                Add(permutedBasis, newV);
            od;
            Sort(permutedBasis);
            if permutedBasis < canonical then
                canonical := permutedBasis;
            fi;
        od;

        return canonical;
    fi;

    # For large k (k! > 120): use column-sorted canonical form.
    # Sort the k symmetric columns (r+1..r+k) lexicographically based on
    # the RREF basis, then re-RREF to get a canonical representative.
    # This is a conservative hash: Sk-equivalent subspaces get the same form,
    # but some non-equivalent ones might too (leading to extra representatives
    # that are safely deduped later by RemoveConjugatesUnderP).
    # Cost: O(k * d * log k) per subspace vs O(k! * k * d) for brute force.
    d := Length(subspace);

    # Extract the k columns from the basis as integer tuples for easy comparison
    colWeights := List([1..k], j ->
        List([1..d], row -> subspace[row][r+j]));

    # Sort column indices by their column vectors (lex order)
    sortedCols := [1..k];
    SortParallel(ShallowCopy(colWeights), sortedCols);

    # Apply the column permutation
    perm := Concatenation([1..r], List([1..k], j -> r + sortedCols[j]));
    permutedBasis := [];
    for v in subspace do
        newV := List([1..n], j -> v[perm[j]]);
        Add(permutedBasis, newV);
    od;
    Sort(permutedBasis);

    return permutedBasis;
end;

# EnumerateSubdirectSubspacesRplusK(r, k)
# Enumerate all subdirect subspaces W ≤ GF(2)^(r+k) such that:
# - W projects surjectively onto the last k coordinates (C2^k part)
# - The projection onto first r coordinates is surjective OR r=0
# Returns list of subspaces as list of basis vectors
#
# OPTIMIZATION: When k > 1, returns orbit representatives under S_k action
# on the last k coordinates. This exploits symmetry from identical C2 factors.
EnumerateSubdirectSubspacesRplusK := function(r, k)
    local n, subspaces, d, pivots, nonPivotCols, freePositions,
          nFree, assignment, matrix, isSubdirect, c, i, temp, one,
          orbitReps, seen, canonical, key, sp;

    n := r + k;
    if n = 0 then
        return [[]];
    fi;

    one := One(GF(2));
    subspaces := [];

    # RREF enumeration: directly construct every d-dimensional subspace
    # of GF(2)^n via its unique reduced row echelon form.
    # Subdirectness requires every column (both first r quotient-map coords
    # and last k C2-factor coords) to have at least one nonzero entry.

    for d in [1..n] do
        if d = n then
            Add(subspaces, IdentityMat(n, GF(2)) * one);
            continue;
        fi;

        for pivots in Combinations([1..n], d) do
            nonPivotCols := Difference([1..n], pivots);

            # Prune: if any non-pivot column is before all pivots,
            # it will always be zero -> not subdirect
            if Length(nonPivotCols) > 0 and nonPivotCols[1] < pivots[1] then
                continue;
            fi;

            # Compute free entry positions: (row, col) pairs
            freePositions := [];
            for i in [1..d] do
                for c in nonPivotCols do
                    if c > pivots[i] then
                        Add(freePositions, [i, c]);
                    fi;
                od;
            od;
            nFree := Length(freePositions);

            for assignment in [0..2^nFree - 1] do
                matrix := NullMat(d, n, GF(2));
                for i in [1..d] do
                    matrix[i][pivots[i]] := one;
                od;
                temp := assignment;
                for i in [1..nFree] do
                    if IsOddInt(temp) then
                        matrix[freePositions[i][1]][freePositions[i][2]] := one;
                    fi;
                    temp := QuoInt(temp, 2);
                od;

                # Subdirect check: all n coordinates must be covered
                # (pivot columns are guaranteed; check non-pivot columns)
                isSubdirect := true;
                for c in nonPivotCols do
                    if ForAll([1..d], i -> IsZero(matrix[i][c])) then
                        isSubdirect := false;
                        break;
                    fi;
                od;

                if isSubdirect then
                    Add(subspaces, List(matrix, row -> List(row)));
                fi;
            od;
        od;
    od;

    # OPTIMIZATION: Deduplicate subspaces under S_k symmetry
    # When k > 1, identical C2 factors can be permuted, so many subspaces
    # are equivalent. Keep only canonical orbit representatives.
    if k > 1 then
        orbitReps := [];
        seen := rec();
        for sp in subspaces do
            canonical := CanonicalSubspaceUnderSk(sp, r, k);
            key := String(canonical);
            if not IsBound(seen.(key)) then
                seen.(key) := true;
                Add(orbitReps, sp);
            fi;
        od;
        return orbitReps;
    fi;

    return subspaces;
end;

# HasOnly2sPartition(partition)
# Check if partition consists only of 2s
HasOnly2sPartition := function(partition)
    return ForAll(partition, d -> d = 2);
end;

# CountLeading2s(partition)
# Count how many leading parts equal 2
CountLeading2s := function(partition)
    local count, i;
    count := 0;
    for i in [1..Length(partition)] do
        if partition[i] = 2 then
            count := count + 1;
        else
            break;
        fi;
    od;
    return count;
end;

# Index2Subgroups(G)
# Find all index-2 subgroups of G (these correspond to quotients G → C2)
Index2Subgroups := function(G)
    local result, D, H, hom, img;

    result := [];

    # Index-2 subgroups are exactly the kernels of homomorphisms G → C2
    # These are determined by the derived subgroup: G' ≤ H ≤ G with [G:H] = 2

    # The derived subgroup is contained in every index-2 subgroup
    D := DerivedSubgroup(G);

    if Size(G) / Size(D) < 2 then
        # G/G' has odd order, no index-2 subgroups
        return [];
    fi;

    # G/G' is abelian; index-2 subgroups of G correspond to index-2 subgroups of G/G'
    # containing the identity
    hom := SafeNaturalHomByNSG(G, D);
    if hom = fail then
        return [];  # Can't compute abelianization
    fi;
    img := ImagesSource(hom);  # G/G' is abelian

    # For each index-2 subgroup of the abelianization, lift back
    for H in MaximalSubgroups(img) do
        if Index(img, H) = 2 then
            Add(result, PreImages(hom, H));
        fi;
    od;

    return result;
end;

# BuildFiberProduct(T, K, c2_pattern, shifted, offsets, numC2, nonC2Start)
# Build a fiber product where T is linked to C2 factors via quotient T → T/K ≅ C2
# c2_pattern specifies which C2 factors are linked (bit pattern)
#
# The fiber product is: {(t, c₁, c₂, ..., cₖ) | φ(t) = Σᵢ linked cᵢ (mod 2)}
# where φ: T → C2 is the quotient map with kernel K.
BuildFiberProduct := function(T, K, c2_pattern, shifted, offsets, numC2, nonC2Start)
    local gens, g, coset, perm, i, off;

    # K is an index-2 subgroup of T
    # Elements of K map to 0 in C2, elements not in K map to 1
    # φ: T → T/K ≅ C2 is the quotient homomorphism

    gens := [];

    # For each generator g of T, build (g, φ(g)) in the fiber product
    for g in GeneratorsOfGroup(T) do
        # Determine φ(g): 0 if g ∈ K, 1 if g ∉ K
        if g in K then
            coset := 0;
        else
            coset := 1;
        fi;

        # Build the C2^k component based on which factors are linked
        perm := ();
        for i in [1..numC2] do
            # Check if this C2 factor is linked (bit i of c2_pattern is set)
            if IsOddInt(QuoInt(c2_pattern, 2^(i-1))) then
                # This C2 is linked; add transposition iff φ(g) = 1
                if coset = 1 then
                    off := offsets[nonC2Start + i];
                    perm := perm * (off + 1, off + 2);
                fi;
            fi;
        od;

        # Add the combined generator: g on T-coordinates, perm on linked C2 coordinates
        Add(gens, g * perm);
    od;

    # For UNlinked C2 factors, add the transposition as an independent generator
    # These C2s are a direct product factor, not part of the fiber structure
    for i in [1..numC2] do
        if not IsOddInt(QuoInt(c2_pattern, 2^(i-1))) then
            off := offsets[nonC2Start + i];
            Add(gens, (off + 1, off + 2));
        fi;
    od;

    gens := Filtered(gens, x -> x <> ());
    if Length(gens) = 0 then
        return Group(());
    fi;

    return Group(gens);
end;

# BuildFiberProductDiagonal(T, K, c2_pattern, shifted, offsets, numC2, nonC2Start)
# Build a "twisted diagonal" fiber product:
# {(t, φ(t)+c, φ(t)+c, ..., c, c, ...) | t ∈ T, c ∈ C2}
# where linked positions get φ(t)+c, and unlinked get c
# This is different from BuildFiberProduct where unlinked positions are independent.
BuildFiberProductDiagonal := function(T, K, c2_pattern, shifted, offsets, numC2, nonC2Start)
    local gens, g, coset, perm, i, off, diag_perm;

    # K is an index-2 subgroup of T
    # φ: T → C2 with ker(φ) = K

    gens := [];

    # For each generator g of T, build (g, φ(g)+0, ..., 0, ...) for c=0
    for g in GeneratorsOfGroup(T) do
        if g in K then
            coset := 0;
        else
            coset := 1;
        fi;

        # For linked positions, add transposition iff φ(g) = 1
        perm := ();
        for i in [1..numC2] do
            if IsOddInt(QuoInt(c2_pattern, 2^(i-1))) then
                if coset = 1 then
                    off := offsets[nonC2Start + i];
                    perm := perm * (off + 1, off + 2);
                fi;
            fi;
            # Unlinked positions get value 0 when c=0, so no transposition here
        od;

        Add(gens, g * perm);
    od;

    # Add the "diagonal" element that moves from c=0 to c=1:
    # All positions (linked and unlinked) flip together
    diag_perm := ();
    for i in [1..numC2] do
        off := offsets[nonC2Start + i];
        diag_perm := diag_perm * (off + 1, off + 2);
    od;
    if diag_perm <> () then
        Add(gens, diag_perm);
    fi;

    gens := Filtered(gens, x -> x <> ());
    if Length(gens) = 0 then
        return Group(());
    fi;

    return Group(gens);
end;

# FindSubdirectsForPartitionWith2s(partition, transFactors, shifted, offsets)
# Special handling for partitions with n₁=2 parts
# Uses fiber product approach from Holt 2010
#
# COMPLETE REWRITE: Uses GF(2) linear algebra to enumerate ALL subdirects
# of T × C2^k correctly. Previous version missed fiber products with
# multiple quotient maps.
#
# Key insight: For T × C2^k where T has r independent quotients to C2:
# 1. Compute Hom(T, C2) which has dimension r over GF(2)
# 2. Subdirects of T × C2^k correspond to subdirect subspaces of C2^r × C2^k
# 3. Enumerate these via linear algebra, then lift back to T × C2^k
FindSubdirectsForPartitionWith2s := function(partition, transFactors, shifted, offsets)
    local k, numC2, nonC2Start, P, subdirects, subspaceReps, subspace, gens, i, j,
          row, perm, baseGens, mixed, mixedShifted, mixedOffs, mixedP,
          combined, off, seen, key, quotientInfo, r, allSubspaces, S, kernels;

    # Count copies of C_2 (from degree-2 parts with C_2 as factor)
    # Partition is sorted descending, so 2s are at the end
    numC2 := 0;
    for i in [Length(partition), Length(partition)-1 .. 1] do
        if partition[i] = 2 then
            numC2 := numC2 + 1;
        else
            break;
        fi;
    od;

    if numC2 < 2 then
        # Not enough C_2 factors for special handling
        return fail;
    fi;

    nonC2Start := Length(partition) - numC2;
    k := numC2;

    # Build the product P for non-C2 factors
    if nonC2Start = 0 then
        # All factors are C_2 - pure elementary abelian case
        subspaceReps := EnumerateSubdirectSubspaces(k);
        subdirects := [];

        for subspace in subspaceReps do
            # Convert subspace to permutation group
            gens := [];
            for row in subspace do
                # Each row gives a generator: product of transpositions
                # where row[i] = 1 means include the i-th transposition
                perm := ();
                for i in [1..k] do
                    if IsOne(row[i]) or row[i] = 1 then
                        off := offsets[Length(partition) - k + i];
                        perm := perm * (off + 1, off + 2);
                    fi;
                od;
                if perm <> () then
                    Add(gens, perm);
                fi;
            od;

            if Length(gens) > 0 then
                Add(subdirects, Group(gens));
            fi;
        od;

        return subdirects;
    fi;

    # Mixed case: some non-C2 factors followed by C2 factors
    # First lift through non-C2 factors, then combine with C2 part
    mixedShifted := shifted{[1..nonC2Start]};
    mixedOffs := offsets{[1..nonC2Start]};

    if Length(mixedShifted) = 1 then
        mixedP := mixedShifted[1];
        baseGens := [mixedP];  # Single factor: just itself
    else
        mixedP := Group(Concatenation(List(mixedShifted, GeneratorsOfGroup)));
        baseGens := FindFPFClassesByLifting(mixedP, mixedShifted, mixedOffs);
    fi;

    subdirects := [];
    seen := rec();

    for mixed in baseGens do
        # Get the quotient maps T → C2 for this base group
        quotientInfo := GetQuotientMapsToC2(mixed);
        r := quotientInfo.dimension;
        kernels := quotientInfo.kernels;

        if r = 0 then
            # T is perfect (or has odd index abelianization), no quotients to C2
            # Only subdirects are direct products T × (subdirect of C2^k)
            subspaceReps := EnumerateSubdirectSubspaces(k);

            for subspace in subspaceReps do
                gens := ShallowCopy(GeneratorsOfGroup(mixed));
                for row in subspace do
                    perm := ();
                    for i in [1..k] do
                        if IsOne(row[i]) or row[i] = 1 then
                            off := offsets[nonC2Start + i];
                            perm := perm * (off + 1, off + 2);
                        fi;
                    od;
                    if perm <> () then
                        Add(gens, perm);
                    fi;
                od;

                combined := Group(gens);
                if IsFPFSubdirect(combined, shifted, offsets) then
                    key := String([Size(combined), SortedList(AbelianInvariants(combined))]);
                    if not IsBound(seen.(key)) then
                        seen.(key) := [];
                    fi;
                    Add(subdirects, combined);
                    Add(seen.(key), combined);
                fi;
            od;
        else
            # T has r independent quotients to C2
            # Subdirects of T × C2^k correspond to subdirect subspaces of C2^(r+k)
            # that project onto all k C2 factors AND are compatible with T-structure

            allSubspaces := EnumerateSubdirectSubspacesRplusK(r, k);

            for subspace in allSubspaces do
                # Build the subdirect from this subspace
                S := BuildSubdirectFromSubspace(mixed, kernels, subspace, shifted, offsets, k, nonC2Start);

                if IsFPFSubdirect(S, shifted, offsets) then
                    key := String([Size(S), SortedList(AbelianInvariants(S))]);
                    if not IsBound(seen.(key)) then
                        seen.(key) := [];
                    fi;
                    Add(subdirects, S);
                    Add(seen.(key), S);
                fi;
            od;
        fi;
    od;

    return subdirects;
end;

###############################################################################
# OPT 3: Generalized C2 Fiber Product
#
# For factor combinations (H1,...,Hk) where each Hi has r_i = dim(Hom(Hi, C2)):
# 1. Total C2 dimension: r = r_1 + ... + r_k
# 2. Subdirect subspaces of GF(2)^r give the "abelian layer" of subdirects
# 3. For each subspace, compute the kernel in H1 x ... x Hk
# 4. Lift through the derived subgroup product D(H1) x ... x D(H_k)
#
# This generalizes FindSubdirectsForPartitionWith2s to handle C2 quotients
# of ALL factors, not just trailing C2 groups.
###############################################################################

FindSubdirectsViaGeneralizedC2 := function(transFactors, shifted, offsets)
    local k, ri, kernelsi, totalR, i, quotientInfo, coordOffsets,
          allSubspaces, subspace, kernelGens, g, row, j, vec, perm,
          off, subdirect, subdirects, gens, coeffs, basisMat, c2cols,
          firstRcols, c2Component, numRepeated, canonical, key, seen,
          orbitReps, repeatedParts, blockSizes;

    k := Length(transFactors);
    if k < 2 then
        return fail;
    fi;

    # Compute C2 dimension and kernels for each factor
    ri := [];
    kernelsi := [];
    totalR := 0;
    for i in [1..k] do
        quotientInfo := GetQuotientMapsToC2(shifted[i]);
        Add(ri, quotientInfo.dimension);
        Add(kernelsi, quotientInfo.kernels);
        totalR := totalR + quotientInfo.dimension;
    od;

    # Need at least total dimension >= 2 for the optimization to be worthwhile
    # Also need at least 2 factors with r_i >= 1
    if totalR < 2 or Number(ri, r -> r >= 1) < 2 then
        return fail;
    fi;

    # Compute coordinate offsets: factor i's C2 coordinates are
    # [coordOffsets[i]+1 .. coordOffsets[i]+ri[i]] in GF(2)^totalR
    coordOffsets := [0];
    for i in [2..k] do
        Add(coordOffsets, coordOffsets[i-1] + ri[i-1]);
    od;

    # Enumerate subdirect subspaces of GF(2)^totalR
    # Subdirectness: projects surjectively onto each factor's C2 coordinates
    # i.e., for each factor i, the columns coordOffsets[i]+1..coordOffsets[i]+ri[i]
    # must all have at least one nonzero entry
    allSubspaces := [];
    # Use RREF enumeration (same method as EnumerateSubdirectSubspacesRplusK)
    allSubspaces := CallFuncList(function()
        local n, subspaces, d, pivots, nonPivotCols, freePositions,
              nFree, assignment, matrix, isSubdirect, c, ii, temp, one,
              factorCols;

        n := totalR;
        if n = 0 then
            return [[]];
        fi;

        one := One(GF(2));
        subspaces := [];

        # Precompute per-factor column ranges for subdirect check
        factorCols := [];
        for ii in [1..k] do
            if ri[ii] > 0 then
                Add(factorCols, [coordOffsets[ii]+1..coordOffsets[ii]+ri[ii]]);
            fi;
        od;

        for d in [1..n] do
            if d = n then
                Add(subspaces, IdentityMat(n, GF(2)) * one);
                continue;
            fi;

            for pivots in Combinations([1..n], d) do
                nonPivotCols := Difference([1..n], pivots);

                if Length(nonPivotCols) > 0 and nonPivotCols[1] < pivots[1] then
                    continue;
                fi;

                freePositions := [];
                for ii in [1..d] do
                    for c in nonPivotCols do
                        if c > pivots[ii] then
                            Add(freePositions, [ii, c]);
                        fi;
                    od;
                od;
                nFree := Length(freePositions);

                for assignment in [0..2^nFree - 1] do
                    matrix := NullMat(d, n, GF(2));
                    for ii in [1..d] do
                        matrix[ii][pivots[ii]] := one;
                    od;
                    temp := assignment;
                    for ii in [1..nFree] do
                        if IsOddInt(temp) then
                            matrix[freePositions[ii][1]][freePositions[ii][2]] := one;
                        fi;
                        temp := QuoInt(temp, 2);
                    od;

                    # Subdirect check: each factor's columns must be covered
                    isSubdirect := true;
                    for c in factorCols do  # c is a range like [start..end]
                        for ii in c do     # ii is a column index
                            if ForAll([1..d], jj -> IsZero(matrix[jj][ii])) then
                                isSubdirect := false;
                                break;
                            fi;
                        od;
                        if not isSubdirect then break; fi;
                    od;

                    if isSubdirect then
                        Add(subspaces, List(matrix, row -> List(row)));
                    fi;
                od;
            od;
        od;

        return subspaces;
    end, []);

    # Deduplicate under symmetry of repeated parts
    # Identify which factors have the same degree and transitive ID
    # (Reuse CanonicalSubspaceUnderSk for blocks of identical factors)
    # For now, keep all subspaces (dedup happens at the normalizer level)

    subdirects := [];
    seen := rec();

    for subspace in allSubspaces do
        # Build the subdirect product for this subspace
        # For each factor i and each generator g of shifted[i]:
        # 1. Compute vec = (phi_1(g), ..., phi_{r_i}(g)) in GF(2)^{r_i}
        # 2. Extend to full GF(2)^totalR vector v with zeros elsewhere
        # 3. Find linear combination of basis rows matching v (SolutionMat)
        # 4. The same combination applied to other factor columns gives the linkage

        gens := [];

        for i in [1..k] do
            for g in GeneratorsOfGroup(shifted[i]) do
                # Compute this generator's quotient map values for factor i
                vec := ListWithIdenticalEntries(totalR, Zero(GF(2)));
                for j in [1..ri[i]] do
                    if not (g in kernelsi[i][j]) then
                        vec[coordOffsets[i] + j] := One(GF(2));
                    fi;
                od;

                # Find combination of subspace basis rows that matches factor i's columns
                basisMat := List(subspace, row -> row{[coordOffsets[i]+1..coordOffsets[i]+ri[i]]});
                firstRcols := vec{[coordOffsets[i]+1..coordOffsets[i]+ri[i]]};

                if ForAll(firstRcols, x -> IsZero(x)) then
                    # g is in all kernels for this factor -> maps to zero
                    # Just add g itself (it doesn't link to other factors)
                    Add(gens, g);
                else
                    coeffs := SolutionMat(basisMat, firstRcols);
                    if coeffs = fail then
                        # g's quotient image is not in the subspace projection
                        # This means g is NOT in the subdirect for this subspace
                        # Skip this generator - the group won't be an FPF subdirect
                        Add(gens, g);
                    else
                        # Compute the linked generator: g * (product of linked factor elements)
                        perm := g;
                        for j in [1..k] do
                            if j <> i and ri[j] > 0 then
                                # Compute the j-th factor's C2 component from the solution
                                c2Component := ListWithIdenticalEntries(ri[j], Zero(GF(2)));
                                for row in [1..Length(subspace)] do
                                    if IsOne(coeffs[row]) then
                                        for c2cols in [1..ri[j]] do
                                            c2Component[c2cols] := c2Component[c2cols] + subspace[row][coordOffsets[j] + c2cols];
                                        od;
                                    fi;
                                od;
                                # For each kernel of factor j that is "active", find an element outside the kernel
                                # and multiply. Since kernels are index-2 subgroups, any element outside is a coset rep.
                                for c2cols in [1..ri[j]] do
                                    if IsOne(c2Component[c2cols]) then
                                        # Need to multiply by a coset representative of kernel[j][c2cols]
                                        # The coset rep is any generator not in the kernel
                                        for row in GeneratorsOfGroup(shifted[j]) do
                                            if not (row in kernelsi[j][c2cols]) then
                                                # Found a coset representative. But we need the quotient
                                                # to be exactly 1, so check if this gen alone suffices
                                                # Actually, for C2 quotient, any element outside kernel
                                                # maps to the non-identity element
                                                perm := perm * row;
                                                break;
                                            fi;
                                        od;
                                    fi;
                                od;
                            fi;
                        od;
                        Add(gens, perm);
                    fi;
                fi;
            od;
        od;

        gens := Filtered(gens, x -> x <> ());
        if Length(gens) = 0 then
            continue;
        fi;

        subdirect := Group(gens);

        # Check FPF
        if IsFPFSubdirect(subdirect, shifted, offsets) then
            Add(subdirects, subdirect);
        fi;
    od;

    return subdirects;
end;

###############################################################################
# ShouldUseGeneralizedC2(transFactors)
#
# Heuristic to decide whether generalized C2 fiber product is beneficial.
# Returns true when the total C2 dimension is >= 2 and at least 2 factors
# contribute, AND no factor has r > 1 (which would cause issues).
###############################################################################

ShouldUseGeneralizedC2 := function(transFactors)
    # DISABLED: The generalized C2 fiber product approach only handles the
    # abelianization layer correctly. For full subdirect enumeration, we'd need
    # to also lift through the derived subgroup product, which is what the
    # standard lifting algorithm already does. Re-enable when the derived
    # subgroup lifting is integrated.
    return false;
end;

###############################################################################
# FPF Subdirect Check
###############################################################################

IsFPFSubdirect := function(U, shifted_factors, offsets)
    local i, factor, offset, degree, moved, gens_proj, projection;

    for i in [1..Length(shifted_factors)] do
        factor := shifted_factors[i];
        offset := offsets[i];
        degree := NrMovedPoints(factor);
        moved := [offset+1..offset+degree];

        gens_proj := List(GeneratorsOfGroup(U), g -> RestrictedPerm(g, moved));
        gens_proj := Filtered(gens_proj, g -> g <> ());

        if Length(gens_proj) = 0 then
            return false;
        fi;

        projection := Group(gens_proj);

        # Cheap check: transitivity (much cheaper than Size for large groups)
        if not IsTransitive(projection, moved) then
            return false;
        fi;

        # Expensive check: exact size comparison (triggers Schreier-Sims)
        if Size(projection) <> Size(factor) then
            return false;
        fi;
    od;
    return true;
end;

###############################################################################
# Phase 5 & 6: Enhanced Invariants and Incremental Deduplication
###############################################################################

# Global variables for passing partition block info to invariant computation.
# Set by FindFPFClassesForPartition before dedup begins.
# CURRENT_BLOCK_RANGES is a list of [start, stop] pairs for each block.
CURRENT_BLOCK_RANGES := [];

# Threshold: if a single combo produces more than this many candidates,
# upgrade from CheapSubgroupInvariantFull to ComputeSubgroupInvariant
# (adds CC cycle-type histogram + 2-subset orbit lengths) for finer buckets.
RICH_DEDUP_THRESHOLD := 1000;

# Chunk size for dedup of large candidate sets. Candidates are processed in
# chunks of this size, with GC and mid-combo checkpoint saves between chunks.
# This prevents OOM on combos with millions of candidates (e.g. [8,4,4,2]).
DEDUP_CHUNK_SIZE := 50000;

# Maximum number of results to store in FPF_SUBDIRECT_CACHE per combo.
# Combos producing more than this are not cached (they consume too much
# memory and won't be reused since caches are cleared per partition).
MAX_CACHE_RESULTS := 100000;

# ComputeSubgroupInvariant(H)
# Compute a rich invariant tuple for subgroup H to minimize false positives
# in conjugacy testing. More discriminating invariants reduce comparisons.
# CheapSubgroupInvariant - fast invariant for partitions with all distinct parts.
# Only computes basic structural properties without element enumeration.
CheapSubgroupInvariant := function(H)
    local inv, sizeH, moved;
    sizeH := Size(H);
    moved := MovedPoints(H);
    inv := [
        sizeH,
        DerivedLength(H),
        Size(Center(H)),
        Size(DerivedSubgroup(H)),
        Exponent(H)
    ];
    if Length(moved) > 0 then
        Add(inv, SortedList(List(Orbits(H, moved), Length)));
    else
        Add(inv, []);
    fi;
    return inv;
end;

# CheapSubgroupInvariantFull(H) - Level 1: fast invariants without ConjugacyClasses.
# Computes structural properties that don't require element enumeration.
# These are sufficient to get bucket sizes of 1-3 for most partitions.
CheapSubgroupInvariantFull := function(H)
    local inv, center, derived, abelianInv, sizeH, moved,
          blockOrbits, blockTIs, k, blockRange, blockPts, orbs, orbLens,
          derivedSizes, D, nc;

    sizeH := Size(H);

    inv := [
        sizeH,
        DerivedLength(H)
    ];

    center := Center(H);
    Add(inv, Size(center));

    derived := DerivedSubgroup(H);
    Add(inv, Size(derived));

    abelianInv := ShallowCopy(AbelianInvariants(H));
    Sort(abelianInv);
    Add(inv, abelianInv);

    Add(inv, Exponent(H));

    moved := MovedPoints(H);
    if Length(moved) > 0 then
        Add(inv, SortedList(List(Orbits(H, moved), Length)));
    else
        Add(inv, []);
    fi;

    derivedSizes := [sizeH, Size(derived)];
    D := derived;
    while Size(D) > 1 and Length(derivedSizes) < 6 do
        D := DerivedSubgroup(D);
        Add(derivedSizes, Size(D));
    od;
    Add(inv, derivedSizes);

    if IsNilpotentGroup(H) then
        nc := NilpotencyClassOfGroup(H);
    else
        nc := -1;
    fi;
    Add(inv, nc);

    # Per-block orbit structure + TransitiveIdentification
    if Length(CURRENT_BLOCK_RANGES) > 0 then
        blockOrbits := [];
        blockTIs := [];
        for k in [1..Length(CURRENT_BLOCK_RANGES)] do
            blockRange := CURRENT_BLOCK_RANGES[k];
            blockPts := [blockRange[1]..blockRange[2]];
            orbs := Orbits(H, blockPts);
            orbLens := SortedList(List(orbs, Length));
            Add(blockOrbits, orbLens);
            if Length(orbs) = 1 then
                Add(blockTIs, [blockRange[2] - blockRange[1] + 1,
                               TransitiveIdentification(Action(H, blockPts))]);
            else
                Add(blockTIs, [blockRange[2] - blockRange[1] + 1, -1]);
            fi;
        od;
        Sort(blockOrbits);
        Add(inv, blockOrbits);
        Sort(blockTIs);
        Add(inv, blockTIs);
    fi;

    return inv;
end;

# ExpensiveSubgroupInvariant(H) - Level 2: ConjugacyClasses + 2-subset orbits.
# Only called when Level 1 bucket has collisions. Very discriminating but costly.
ExpensiveSubgroupInvariant := function(H)
    local inv, moved, sizeH, classes, cl, cycleType, classHist,
          pairs, pairOrbLens;

    sizeH := Size(H);
    moved := MovedPoints(H);
    inv := [];

    # Cycle type histogram via conjugacy classes
    if sizeH <= 10000 then
        classes := ConjugacyClasses(H);
        classHist := rec();
        for cl in classes do
            cycleType := String(SortedList(CycleLengths(Representative(cl), moved)));
            if IsBound(classHist.(cycleType)) then
                classHist.(cycleType) := classHist.(cycleType) + Size(cl);
            else
                classHist.(cycleType) := Size(cl);
            fi;
        od;
        Add(inv, classHist);
    else
        Add(inv, -1);
    fi;

    # 2-subset orbit structure
    if Length(moved) > 0 and Length(moved) <= 20 then
        pairs := Combinations(moved, 2);
        pairOrbLens := SortedList(List(Orbits(H, pairs, OnSets), Length));
        Add(inv, pairOrbLens);
    else
        Add(inv, -1);
    fi;

    return inv;
end;

# ComputeSubgroupInvariant(H) - Full invariant (both levels combined).
# Used by RemoveConjugatesUnderN for batch dedup.
ComputeSubgroupInvariant := function(H)
    local inv;
    inv := CheapSubgroupInvariantFull(H);
    Append(inv, ExpensiveSubgroupInvariant(H));
    return inv;
end;

# InvariantsMatch(inv1, inv2)
# Check if two invariant tuples match (compatible for conjugacy)
InvariantsMatch := function(inv1, inv2)
    local i;

    if Length(inv1) <> Length(inv2) then
        return false;
    fi;

    for i in [1..Length(inv1)] do
        if inv1[i] <> inv2[i] then
            return false;
        fi;
    od;

    return true;
end;

# IsConjugateToAnyInBucket(N, H, bucket, inv)
# Check if H is conjugate to any group in bucket under N
# Uses pre-computed invariant to skip incompatible groups
IsConjugateToAnyInBucket := function(N, H, bucket, inv)
    local rep;

    for rep in bucket do
        if RepresentativeAction(N, H, rep) <> fail then
            return true;
        fi;
    od;
    return false;
end;

# AddIfNotConjugate(N, H, reps, byInvariant, invFunc)
# Add H to reps if not conjugate to any existing rep
# Returns true if added, false if duplicate
AddIfNotConjugate := function(N, H, reps, byInvariant, invFunc)
    local inv, key;

    inv := invFunc(H);
    key := InvariantKey(inv);

    if IsBound(byInvariant.(key)) then
        if IsConjugateToAnyInBucket(N, H, byInvariant.(key), inv) then
            return false;
        fi;
    else
        byInvariant.(key) := [];
    fi;

    Add(reps, H);
    Add(byInvariant.(key), H);
    return true;
end;

###############################################################################
# Canonical Form Deduplication via 'images' package
#
# Replaces O(K^2) pairwise RepresentativeAction with O(K) canonical form
# computation using MinimalImage. Two subgroups H1, H2 <= Sym(n) are conjugate
# under N iff their canonical forms (action tables under N) are equal.
###############################################################################

# EncodeConjugationAction(N, deg)
# Encode N's conjugation action as a permutation group on {1..deg^2}.
# Under conjugation by sigma, the pair (i, j) maps to (sigma(i), sigma(j)).
EncodeConjugationAction := function(N, deg)
    local gens, encodedGens, g, img, i, j;
    gens := GeneratorsOfGroup(N);
    encodedGens := [];
    for g in gens do
        img := [];
        for i in [1..deg] do
            for j in [1..deg] do
                img[(i-1)*deg + j] := (i^g - 1)*deg + j^g;
            od;
        od;
        Add(encodedGens, PermList(img));
    od;
    if Length(encodedGens) = 0 then
        return Group(());
    fi;
    return Group(encodedGens);
end;

# ActionTable(H, deg)
# Compute the action table of H as a subset of {1..deg^2}.
# T(H) = { (i-1)*deg + i^h : i in {1..deg}, h in H }
ActionTable := function(H, deg)
    local table, h, i;
    table := [];
    for h in H do
        for i in [1..deg] do
            AddSet(table, (i-1)*deg + i^h);
        od;
    od;
    return table;
end;

# CanonicalSubgroupForm(N_encoded, H, deg)
# Compute canonical form of subgroup H under N-conjugacy using MinimalImage.
# Returns fail if images package unavailable or group too large.
#
# Uses set-of-sets encoding: each element h is encoded as its point-image set
# S(h) = {(i-1)*deg + i^h : i = 1..deg}, and the subgroup is F(H) = {S(h) : h in H}.
# This is faithful (H1 = H2 iff F(H1) = F(H2)) and compatible with conjugation
# (sigma maps F(H) to F(sigma*H*sigma^-1) via OnSetsSets).
CanonicalSubgroupForm := function(N_encoded, H, deg)
    local faithful_table, sizeH;
    if not IMAGES_AVAILABLE then return fail; fi;

    sizeH := Size(H);

    # Set-of-sets encoding: F(H) = {S(h) : h in H} where S(h) = {(i-1)*deg + i^h : i=1..deg}.
    # This is faithful: F(H1) = F(H2) iff H1 = H2, and compatible with N-conjugation
    # via OnSetsSets action. MinimalImage with OnSetsSets can be expensive for large |H|.
    # Fall back to pairwise RepresentativeAction for large groups.
    if sizeH > 200 then return fail; fi;

    faithful_table := Set(List(H, h ->
        Set([1..deg], i -> (i-1)*deg + i^h)));

    return MinimalImage(N_encoded, faithful_table, OnSetsSets);
end;

###############################################################################
# Conjugacy Deduplication with Normalizer (KEY OPTIMIZATION)
###############################################################################

# Use normalizer N instead of full S_n - this is the main speedup!
# Now uses enhanced invariants (Phase 6) for better bucketing
RemoveConjugatesUnderN := function(N, subgroups)
    local reps, repInvs, byInvariant, H, inv, key, found, rep, i;

    if Length(subgroups) = 0 then
        return [];
    fi;

    # Bucket by enhanced invariants for fewer false positive comparisons
    byInvariant := rec();
    for H in subgroups do
        inv := ComputeSubgroupInvariant(H);
        key := InvariantKey(inv);
        if not IsBound(byInvariant.(key)) then
            byInvariant.(key) := [];
        fi;
        Add(byInvariant.(key), [H, inv]);
    od;

    reps := [];
    repInvs := [];
    for key in RecNames(byInvariant) do
        for H in byInvariant.(key) do
            found := false;
            # Only compare within the same invariant bucket
            for i in [1..Length(reps)] do
                if InvariantsMatch(H[2], repInvs[i]) then
                    if RepresentativeAction(N, H[1], reps[i]) <> fail then
                        found := true;
                        break;
                    fi;
                fi;
            od;
            if not found then
                Add(reps, H[1]);
                Add(repInvs, H[2]);
            fi;
        od;
    od;

    return reps;
end;

###############################################################################
# Find FPF classes for a partition - Full enumeration + Normalizer dedup
###############################################################################

###############################################################################
# Checkpoint support for FindFPFClassesForPartition
# Saves progress after each combo so computation can be resumed.
###############################################################################

# Global checkpoint directory. Set before calling FindFPFClassesForPartition.
# When set to a non-empty string, enables checkpointing.
# Example: CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/checkpoints";
if not IsBound(CHECKPOINT_DIR) then
    CHECKPOINT_DIR := "";
fi;

# Global combo output directory. Set before calling FindFPFClassesForPartition.
# When set to a non-empty string, writes per-combo result files to this directory.
# Example: COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17_v2/[8,6,3]";
if not IsBound(COMBO_OUTPUT_DIR) then
    COMBO_OUTPUT_DIR := "";
fi;


# Back up a file to .bak before overwriting.
# Preserves last good state in case of crash during write.
_BackupFile := function(filepath)
    local bakPath, inp, content, out;
    if not IsExistingFile(filepath) then return; fi;
    bakPath := Concatenation(filepath, ".bak");
    # Read existing file content
    inp := InputTextFile(filepath);
    if inp = fail then return; fi;
    content := ReadAll(inp);
    CloseStream(inp);
    if content = fail then return; fi;
    # Write to backup
    out := OutputTextFile(bakPath, false);
    if out = fail then return; fi;
    WriteAll(out, content);
    CloseStream(out);
end;

_SaveCheckpoint := function(ckptFile, completedKeys, all_fpf,
                            totalCandidates, addedCount, invKeys...)
    local i, gens, s, _invKeys;

    # invKeys is optional - list of precomputed invariant key strings
    if Length(invKeys) > 0 then
        _invKeys := invKeys[1];
    else
        _invKeys := fail;
    fi;

    # Back up existing checkpoint before overwriting
    _BackupFile(ckptFile);

    # Write checkpoint (backup preserves previous good state)
    PrintTo(ckptFile, "# Checkpoint file - auto-generated\n");
    AppendTo(ckptFile, "# ", Length(completedKeys), " combos, ",
             Length(all_fpf), " groups\n\n");

    AppendTo(ckptFile, "_CKPT_COMPLETED_KEYS := [\n");
    for i in [1..Length(completedKeys)] do
        AppendTo(ckptFile, "\"", completedKeys[i], "\"");
        if i < Length(completedKeys) then
            AppendTo(ckptFile, ",\n");
        fi;
    od;
    AppendTo(ckptFile, "\n];\n\n");

    AppendTo(ckptFile, "_CKPT_TOTAL_CANDIDATES := ", totalCandidates, ";\n");
    AppendTo(ckptFile, "_CKPT_ADDED_COUNT := ", addedCount, ";\n\n");

    # Save all_fpf as generator lists
    AppendTo(ckptFile, "_CKPT_ALL_FPF_GENS := [\n");
    for i in [1..Length(all_fpf)] do
        gens := GeneratorsOfGroup(all_fpf[i]);
        s := "";
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        fi;
        AppendTo(ckptFile, "[", s, "]");
        if i < Length(all_fpf) then
            AppendTo(ckptFile, ",\n");
        else
            AppendTo(ckptFile, "\n");
        fi;
    od;
    AppendTo(ckptFile, "];\n");

    # Save invariant keys for fast reload (avoids recomputing invariants)
    if _invKeys <> fail and Length(_invKeys) = Length(all_fpf) then
        AppendTo(ckptFile, "\n_CKPT_INV_KEYS := [\n");
        for i in [1..Length(_invKeys)] do
            AppendTo(ckptFile, "\"", _invKeys[i], "\"");
            if i < Length(_invKeys) then
                AppendTo(ckptFile, ",\n");
            else
                AppendTo(ckptFile, "\n");
            fi;
        od;
        AppendTo(ckptFile, "];\n");
    fi;
end;

# Append-based checkpoint: writes only the NEW groups from this combo.
# Convert a cache key like "[ [ 3, 1 ], [ 6, 1 ], [ 8, 1 ] ]" to a filename
# like "[3,1]_[6,1]_[8,1].g" (strip spaces, remove outer brackets, join with _).
_CacheKeyToFileName := function(cacheKey)
    local i, result, s;
    # Strip all spaces
    result := "";
    for i in [1..Length(cacheKey)] do
        if cacheKey[i] <> ' ' then
            Append(result, [cacheKey[i]]);
        fi;
    od;
    # Remove outermost brackets: "[[3,1],[6,1],[8,1]]" -> "[3,1],[6,1],[8,1]"
    if Length(result) >= 2 and result[1] = '[' and result[Length(result)] = ']' then
        result := result{[2..Length(result)-1]};
    fi;
    # Replace "],[" with "]_["
    s := "";
    i := 1;
    while i <= Length(result) do
        if i + 2 <= Length(result) and result{[i..i+2]} = "],[" then
            Append(s, "]_[");
            i := i + 3;
        else
            Add(s, result[i]);
            i := i + 1;
        fi;
    od;
    Append(s, ".g");
    return s;
end;


# Write per-combo results to a separate file in COMBO_OUTPUT_DIR.
# Each file contains header comments (combo key, counts, timing)
# and one line per group with its generators.
_WriteComboResults := function(dir, cacheKey, groups, candidateCount, elapsedMs)
    local fileName, filePath, i, gens, s;
    fileName := _CacheKeyToFileName(cacheKey);
    filePath := Concatenation(dir, "/", fileName);
    # Header
    PrintTo(filePath, "# combo: ", cacheKey, "\n");
    AppendTo(filePath, "# candidates: ", candidateCount, "\n");
    AppendTo(filePath, "# deduped: ", Length(groups), "\n");
    AppendTo(filePath, "# elapsed_ms: ", elapsedMs, "\n");
    # Generator lines
    for i in [1..Length(groups)] do
        gens := GeneratorsOfGroup(groups[i]);
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        AppendTo(filePath, "[", s, "]\n");
    od;
end;


# Each combo appends a delta record to a .log file. On resume, all deltas
# are replayed to reconstruct the full state. No full rewrite needed.
_AppendCheckpointDelta := function(ckptLogFile, comboKey, newGroups,
                                    totalCandidates, addedCount, totalFpf,
                                    newInvKeys...)
    local i, gens, s, _invKeys;

    # newInvKeys is optional vararg: list of invariant key strings
    if Length(newInvKeys) > 0 then
        _invKeys := newInvKeys[1];
    else
        _invKeys := [];
    fi;

    # Each delta is a self-contained GAP block that appends to lists
    AppendTo(ckptLogFile, "# combo: ", comboKey, "\n");
    AppendTo(ckptLogFile, "Add(_CKPT_COMPLETED_KEYS, \"", comboKey, "\");\n");
    AppendTo(ckptLogFile, "_CKPT_TOTAL_CANDIDATES := ", totalCandidates, ";\n");
    AppendTo(ckptLogFile, "_CKPT_ADDED_COUNT := ", addedCount, ";\n");
    for i in [1..Length(newGroups)] do
        gens := GeneratorsOfGroup(newGroups[i]);
        s := "";
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        fi;
        AppendTo(ckptLogFile, "Add(_CKPT_ALL_FPF_GENS, [", s, "]);\n");
        # Save invariant key alongside generators (for fast byInvariant rebuild)
        if i <= Length(_invKeys) then
            AppendTo(ckptLogFile, "Add(_CKPT_ALL_INV_KEYS, \"",
                     _invKeys[i], "\");\n");
        fi;
    od;
    AppendTo(ckptLogFile, "# end combo (", totalFpf, " total fpf)\n\n");
end;

_LoadCheckpointLog := function(ckptLogFile)
    local result;
    if not IsExistingFile(ckptLogFile) then
        return fail;
    fi;
    # Initialize accumulators; the log file's Add() calls build them up
    _CKPT_COMPLETED_KEYS := [];
    _CKPT_ALL_FPF_GENS := [];
    _CKPT_ALL_INV_KEYS := [];  # Invariant keys (saved alongside gens)
    _CKPT_TOTAL_CANDIDATES := 0;
    _CKPT_ADDED_COUNT := 0;
    Read(ckptLogFile);
    result := rec(
        completedKeys := _CKPT_COMPLETED_KEYS,
        allFpfGens := _CKPT_ALL_FPF_GENS,
        totalCandidates := _CKPT_TOTAL_CANDIDATES,
        addedCount := _CKPT_ADDED_COUNT
    );
    # Attach inv keys if present (backward compatible: old logs won't have them)
    if Length(_CKPT_ALL_INV_KEYS) = Length(_CKPT_ALL_FPF_GENS) then
        result.invKeys := _CKPT_ALL_INV_KEYS;
    fi;
    Unbind(_CKPT_COMPLETED_KEYS);
    Unbind(_CKPT_ALL_FPF_GENS);
    Unbind(_CKPT_ALL_INV_KEYS);
    Unbind(_CKPT_TOTAL_CANDIDATES);
    Unbind(_CKPT_ADDED_COUNT);
    return result;
end;

_LoadCheckpoint := function(ckptFile)
    local result;
    if not IsExistingFile(ckptFile) then
        return fail;
    fi;
    _CKPT_COMPLETED_KEYS := [];
    _CKPT_ALL_FPF_GENS := [];
    _CKPT_TOTAL_CANDIDATES := 0;
    _CKPT_ADDED_COUNT := 0;
    _CKPT_INV_KEYS := fail;  # Optional: saved invariant keys
    _CKPT_RICH_INV := false;  # Optional: rich invariant flag
    Read(ckptFile);
    result := rec(
        completedKeys := _CKPT_COMPLETED_KEYS,
        allFpfGens := _CKPT_ALL_FPF_GENS,
        totalCandidates := _CKPT_TOTAL_CANDIDATES,
        addedCount := _CKPT_ADDED_COUNT,
        richInvActive := _CKPT_RICH_INV
    );
    if _CKPT_INV_KEYS <> fail then
        result.invKeys := _CKPT_INV_KEYS;
    fi;
    Unbind(_CKPT_COMPLETED_KEYS);
    Unbind(_CKPT_ALL_FPF_GENS);
    Unbind(_CKPT_TOTAL_CANDIDATES);
    Unbind(_CKPT_ADDED_COUNT);
    Unbind(_CKPT_INV_KEYS);
    Unbind(_CKPT_RICH_INV);
    return result;
end;

FindFPFClassesForPartition := function(n, partition)
    local transitiveLists, all_fpf, allInvKeys, N, startTime, IterateCombinations,
          numTrailing2s, useC2Opt, i, byInvariant, invFunc, addedCount,
          totalCandidates, incrementalDedup, off_acc,
          ckptFile, ckptLogFile, ckptData, completedKeySet, completedKeyList,
          comboCount, lastCkptTime, partStr, gens, H, fpfBeforeCombo,
          usePerComboNorm, comboNormCache, currentN, _richInvActive;

    startTime := Runtime();

    # Count trailing 2s to decide if we use C2 optimization
    numTrailing2s := 0;
    for i in [Length(partition), Length(partition)-1 .. 1] do
        if partition[i] = 2 then
            numTrailing2s := numTrailing2s + 1;
        else
            break;
        fi;
    od;
    # C2 optimization is enabled for partitions with 2+ trailing 2s.
    # A guard check ensures non-C2 factors have small abelianization (r ≤ 1)
    # to avoid duplicate enumeration with groups like V4 (r=2) or D8 (r=3).
    useC2Opt := numTrailing2s >= 2;

    transitiveLists := List(partition, d ->
        List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));

    # Build normalizer early for incremental deduplication
    N := BuildConjugacyTestGroup(n, partition);

    # Per-combo normalizer optimization for all multi-part partitions.
    # Key insight: FPF subdirects project surjectively onto each factor,
    # so any conjugating element must normalize each factor T_k.
    # Conjugacy under N = S_{d1} x ... x S_{dk} (+ block swaps) equals
    # conjugacy under N_{S_{d1}}(T_1) x ... x N_{S_{dk}}(T_k) (+ block swaps
    # only for positions with same (degree, TI)).
    usePerComboNorm := Length(partition) >= 2;
    comboNormCache := rec();
    currentN := N;  # Will be overridden per-combo when usePerComboNorm=true

    # Set global block ranges for per-block invariant computation (Phase A2)
    CURRENT_BLOCK_RANGES := [];
    off_acc := 0;
    for i in [1..Length(partition)] do
        Add(CURRENT_BLOCK_RANGES, [off_acc + 1, off_acc + partition[i]]);
        off_acc := off_acc + partition[i];
    od;

    all_fpf := [];
    allInvKeys := [];
    byInvariant := rec();
    addedCount := 0;
    totalCandidates := 0;
    completedKeySet := rec();
    completedKeyList := [];
    comboCount := 0;
    lastCkptTime := Runtime();

    # Choose invariant function based on partition structure.
    # For partitions with repeated block sizes, N includes block permutations,
    # creating large dedup rates. Use the full (expensive) invariant with
    # ConjugacyClasses histogram — this is essential for near-perfect bucketing.
    # For 2-part distinct partitions (e.g., [9,8]), N = S_a x S_b is MUCH larger
    # than P = T_a x T_b, so RepresentativeAction(N,...) is very expensive.
    # Per-block TransitiveIdentification is NOT discriminating enough because all
    # subdirect products of T1 x T2 project surjectively to both factors, giving
    # identical per-block TI. Need ConjugacyClasses of the FULL group to capture
    # the inter-block linking structure (cycle type histogram).
    # Use ComputeSubgroupInvariant (rich invariants) for all partitions.
    # Adds CC cycle-type histogram + 2-subset orbit lengths on top of cheap
    # invariants. Much finer bucketing → dramatically faster dedup for large
    # combos (e.g., 11K candidates in S17 [6,4,4,3]). Computation cost is
    # negligible for groups with moved points ≤ 20 and orders < 10000.
    invFunc := ComputeSubgroupInvariant;
    _richInvActive := true;



    # Checkpoint: build file path and try to load existing checkpoint
    ckptFile := "";
    ckptLogFile := "";
    if CHECKPOINT_DIR <> "" then
        partStr := JoinStringsWithSeparator(List(partition, String), "_");
        ckptFile := Concatenation(CHECKPOINT_DIR, "/ckpt_", String(n), "_",
                                   partStr, ".g");
        ckptLogFile := Concatenation(CHECKPOINT_DIR, "/ckpt_", String(n), "_",
                                      partStr, ".log");
        # Load monolithic .g first as base, then apply .log deltas on top.
        # Previously: .log was tried first and .g was fallback, which caused
        # data loss when .log had only partial deltas without the .g base.
        Print("  CHECKPOINT: Loading base .g file...\n");
        ckptData := _LoadCheckpoint(ckptFile);
        if ckptData <> fail then
            Print("  CHECKPOINT: Base loaded: ", Length(ckptData.allFpfGens),
                  " groups, ", Length(ckptData.completedKeys), " combos\n");
        fi;
        if IsExistingFile(ckptLogFile) then
            Print("  CHECKPOINT: Loading .log deltas...\n");
            # Apply .log deltas on top of .g base (or empty if no .g)
            if ckptData <> fail then
                _CKPT_COMPLETED_KEYS := ckptData.completedKeys;
                _CKPT_ALL_FPF_GENS := ckptData.allFpfGens;
                _CKPT_TOTAL_CANDIDATES := ckptData.totalCandidates;
                _CKPT_ADDED_COUNT := ckptData.addedCount;
            else
                _CKPT_COMPLETED_KEYS := [];
                _CKPT_ALL_FPF_GENS := [];
                _CKPT_TOTAL_CANDIDATES := 0;
                _CKPT_ADDED_COUNT := 0;
            fi;
            Read(ckptLogFile);
            # Preserve invKeys from .g base if available.
            # They cover the first N groups (from .g); remaining groups (from .log)
            # will have their inv keys recomputed during indexing.
            if ckptData <> fail and IsBound(ckptData.invKeys) then
                _CKPT_INV_KEYS := ckptData.invKeys;
            else
                _CKPT_INV_KEYS := fail;
            fi;
            ckptData := rec(
                completedKeys := _CKPT_COMPLETED_KEYS,
                allFpfGens := _CKPT_ALL_FPF_GENS,
                totalCandidates := _CKPT_TOTAL_CANDIDATES,
                addedCount := _CKPT_ADDED_COUNT,
                richInvActive := (ckptData <> fail and IsBound(ckptData.richInvActive)
                                   and ckptData.richInvActive = true)
            );
            if _CKPT_INV_KEYS <> fail then
                ckptData.invKeys := _CKPT_INV_KEYS;
            fi;
            Unbind(_CKPT_COMPLETED_KEYS);
            Unbind(_CKPT_ALL_FPF_GENS);
            Unbind(_CKPT_TOTAL_CANDIDATES);
            Unbind(_CKPT_ADDED_COUNT);
            Unbind(_CKPT_INV_KEYS);
            Print("  CHECKPOINT: Deltas applied: ", Length(ckptData.allFpfGens),
                  " groups total, ", Length(ckptData.completedKeys), " combos\n");
            # Deduplicate completed keys and generators.
            # Non-atomic .g save + .log truncation can cause overlap:
            # if a crash occurs between saving .g and truncating .log,
            # the next load reads the same data from both files.
            _dedup_keys := rec();
            _dedup_gens := [];
            _dedup_inv_keys := fail;
            if IsBound(ckptData.invKeys) then
                _dedup_inv_keys := [];
            fi;
            _dedup_removed := 0;
            for _di in [1..Length(ckptData.completedKeys)] do
                _dk := ckptData.completedKeys[_di];
                if not IsBound(_dedup_keys.(_dk)) then
                    _dedup_keys.(_dk) := true;
                else
                    _dedup_removed := _dedup_removed + 1;
                fi;
            od;
            # Always run generator dedup: orphaned groups from partial combos
            # (crash during in-progress combo) may exist without a matching combo key.
            if true then
                if _dedup_removed > 0 then
                    Print("  CHECKPOINT DEDUP: ", _dedup_removed,
                          " duplicate combo keys found.\n");
                fi;
                Print("  CHECKPOINT DEDUP: deduplicating generators...\n");
                # Rebuild: replay combo keys in order, keep only first occurrence's groups
                _dedup_keys := rec();
                _dedup_combo_list := [];
                _dedup_gens := [];
                if IsBound(ckptData.invKeys) then
                    _dedup_inv_keys := [];
                fi;
                _gi := 1;  # generator index tracking
                # The .log appends via Add(_CKPT_ALL_FPF_GENS, genList) per group
                # and Add(_CKPT_COMPLETED_KEYS, key) per combo.
                # Groups are interleaved between combo keys:
                # key1, groups_for_key1..., key2, groups_for_key2..., etc.
                # But after merge, allFpfGens is a flat list and completedKeys
                # is a flat list - they're not directly correlated.
                # The safest dedup is string-based on generator lists.
                _seen_gens := rec();
                _unique_gens := [];
                if IsBound(ckptData.invKeys) then
                    _unique_inv := [];
                fi;
                for _di in [1..Length(ckptData.allFpfGens)] do
                    _gkey := String(ckptData.allFpfGens[_di]);
                    if not IsBound(_seen_gens.(_gkey)) then
                        _seen_gens.(_gkey) := true;
                        Add(_unique_gens, ckptData.allFpfGens[_di]);
                        if IsBound(ckptData.invKeys) and _di <= Length(ckptData.invKeys) then
                            Add(_unique_inv, ckptData.invKeys[_di]);
                        fi;
                    fi;
                od;
                # Deduplicate completed keys list
                _dedup_keys := rec();
                _dedup_combo_list := [];
                for _di in [1..Length(ckptData.completedKeys)] do
                    _dk := ckptData.completedKeys[_di];
                    if not IsBound(_dedup_keys.(_dk)) then
                        _dedup_keys.(_dk) := true;
                        Add(_dedup_combo_list, _dk);
                    fi;
                od;
                Print("  CHECKPOINT DEDUP: ", Length(ckptData.allFpfGens), " -> ",
                      Length(_unique_gens), " groups, ",
                      Length(ckptData.completedKeys), " -> ",
                      Length(_dedup_combo_list), " combos\n");
                ckptData.allFpfGens := _unique_gens;
                ckptData.completedKeys := _dedup_combo_list;
                if IsBound(ckptData.invKeys) and Length(_unique_inv) > 0 then
                    ckptData.invKeys := _unique_inv;
                else
                    Unbind(ckptData.invKeys);
                fi;
            fi;
        fi;
        if ckptData <> fail then
            Print("  CHECKPOINT: Rebuilding groups from ", Length(ckptData.allFpfGens),
                  " generator sets...\n");
            # Rebuild all_fpf from saved generators
            for i in [1..Length(ckptData.allFpfGens)] do
                gens := ckptData.allFpfGens[i];
                if Length(gens) > 0 then
                    H := Group(gens);
                else
                    H := Group(());
                fi;
                Add(all_fpf, H);
                if i mod 1000 = 0 then
                    Print("    rebuilt ", i, "/", Length(ckptData.allFpfGens), " groups\n");
                fi;
            od;
            # Check if checkpoint was saved with rich invariants
            if IsBound(ckptData.richInvActive) and ckptData.richInvActive = true then
                _richInvActive := true;
                invFunc := ComputeSubgroupInvariant;
                Print("  CHECKPOINT: Rich invariants active (restored from checkpoint)\n");
            fi;
            # Per-combo dedup: no need to rebuild byInvariant on restore.
            # The multiset of (degree, TI) is a conjugacy invariant, so
            # cross-combo duplicates are impossible. Each combo resets its own index.
            # Just load allInvKeys for checkpoint saving.
            if IsBound(ckptData.invKeys) then
                allInvKeys := ckptData.invKeys;
                Print("  CHECKPOINT: Loaded ", Length(allInvKeys), " invariant keys\n");
            fi;
            totalCandidates := ckptData.totalCandidates;
            addedCount := ckptData.addedCount;
            # Build completed key set for O(1) lookup
            for i in [1..Length(ckptData.completedKeys)] do
                completedKeySet.(ckptData.completedKeys[i]) := true;
                Add(completedKeyList, ckptData.completedKeys[i]);
            od;
            Print("  CHECKPOINT: Restored ", Length(all_fpf), " groups, ",
                  Length(completedKeyList), " combos. Ready.\n");
            # Save monolithic checkpoint with inv keys for faster future restarts
            if ckptFile <> "" and Length(allInvKeys) = Length(all_fpf) then
                Print("  CHECKPOINT: Saving with invariant keys for fast reload...\n");
                _SaveCheckpoint(ckptFile, completedKeyList, all_fpf,
                                totalCandidates, addedCount, allInvKeys);
                AppendTo(ckptFile, "\n_CKPT_RICH_INV := ", _richInvActive, ";\n");
                # Truncate the .log file since all its content is now in the .g file.
                # This prevents the .log overlay from accumulating stale deltas and
                # ensures inv keys are preserved on future restarts.
                if ckptLogFile <> "" and IsExistingFile(ckptLogFile) then
                    _BackupFile(ckptLogFile);
                    PrintTo(ckptLogFile, "# Merged into .g checkpoint\n");
                fi;
                Print("  CHECKPOINT: Saved (log truncated).\n");
            fi;
        fi;
    fi;

    # Helper to add results with incremental deduplication.
    # Uses pairwise RepresentativeAction with enhanced invariant bucketing.
    # For 2-part distinct partitions, uses per-combo normalizer (currentN)
    # which is vastly smaller than the full S_a x S_b.
    #
    # Chunked dedup: for large candidate sets (>50K), processes in chunks
    # of DEDUP_CHUNK_SIZE, nulling out processed entries and forcing GC
    # between chunks to keep memory bounded. Saves mid-combo checkpoint
    # after each chunk so dedup progress survives crashes.
    incrementalDedup := function(newResults)
        local H, before, _dedupIdx, _dedupTotal, _lastDedupProgress, _beforeAdd,
              _chunkStart, _chunkEnd, _i, _lastCkptPos, _inv, _key, _preIdx;
        # Rebuild byInvariant index. Normally cross-combo duplicates are
        # impossible (different factor types → different invariants), so a
        # fresh rec() suffices. But after a mid-combo checkpoint resume,
        # partial groups from the interrupted combo are in all_fpf and MUST
        # be indexed to prevent re-addition. We detect this by checking for
        # _dedup_partial_ keys in completedKeySet.
        byInvariant := rec();
        if Length(all_fpf) > 0 and ForAny(completedKeyList,
                k -> Length(k) >= 15 and k{[1..15]} = "_dedup_partial_") then
            Print("    [dedup] mid-combo resume detected, rebuilding index from ",
                  Length(all_fpf), " existing groups...\n");
            if Length(allInvKeys) = Length(all_fpf) then
                # Fast path: use saved invariant keys (no recomputation needed)
                for _preIdx in [1..Length(all_fpf)] do
                    _key := allInvKeys[_preIdx];
                    if not IsBound(byInvariant.(_key)) then
                        byInvariant.(_key) := [];
                    fi;
                    Add(byInvariant.(_key), all_fpf[_preIdx]);
                od;
                Print("    [dedup] indexed ", Length(all_fpf),
                      " groups from saved keys (0 recomputed)\n");
            else
                # Slow path: recompute invariants (old checkpoint without keys)
                Print("    [dedup] no saved inv keys, recomputing...\n");
                for _preIdx in [1..Length(all_fpf)] do
                    _inv := invFunc(all_fpf[_preIdx]);
                    _key := InvariantKey(_inv);
                    if not IsBound(byInvariant.(_key)) then
                        byInvariant.(_key) := [];
                    fi;
                    Add(byInvariant.(_key), all_fpf[_preIdx]);
                od;
                Print("    [dedup] indexed ", Length(all_fpf),
                      " groups (recomputed), ", Length(RecNames(byInvariant)),
                      " buckets\n");
            fi;
        fi;
        before := Length(all_fpf);
        totalCandidates := totalCandidates + Length(newResults);
        # Upgrade to richer invariants when a combo produces many candidates
        if Length(newResults) > RICH_DEDUP_THRESHOLD and not _richInvActive then
            _richInvActive := true;
            invFunc := ComputeSubgroupInvariant;
            Print("  UPGRADING to rich invariants (CC histogram + 2-subset orbits)...\n");
        fi;
        _dedupIdx := 0;
        _dedupTotal := Length(newResults);
        _lastDedupProgress := Runtime();
        _lastCkptPos := before;  # tracks last checkpoint position in all_fpf
        _chunkStart := 1;
        while _chunkStart <= _dedupTotal do
            _chunkEnd := Minimum(_chunkStart + DEDUP_CHUNK_SIZE - 1, _dedupTotal);
            for _i in [_chunkStart.._chunkEnd] do
                H := newResults[_i];
                _dedupIdx := _dedupIdx + 1;
                # Progress logging for long dedup (every 60s)
                if _dedupTotal > 50 and Runtime() - _lastDedupProgress > 60000 then
                    Print("      [dedup] ", _dedupIdx, "/", _dedupTotal,
                          " checked, ", Length(all_fpf) - before, " new so far (",
                          Length(all_fpf), " total, ",
                          Int((Runtime() - _lastDedupProgress)/1000 + 60), "s)\n");
                    _lastDedupProgress := Runtime();
                    if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
                        PrintTo(_HEARTBEAT_FILE, "alive ",
                                Int(Runtime() / 1000), "s dedup ",
                                _dedupIdx, "/", _dedupTotal, "\n");
                    fi;
                fi;
                _beforeAdd := Length(all_fpf);
                if AddIfNotConjugate(currentN, H, all_fpf, byInvariant, invFunc) then
                    addedCount := addedCount + 1;
                    # Track invariant key for checkpoint fast-reload
                    Add(allInvKeys, InvariantKey(invFunc(H)));
                fi;
                # Null out processed entry so GC can reclaim the group object
                newResults[_i] := 0;
            od;
            # Between chunks: force garbage collection to reclaim nulled entries
            if _dedupTotal > DEDUP_CHUNK_SIZE and _chunkEnd < _dedupTotal then
                GASMAN("collect");
                Print("      [dedup chunk] ", _chunkEnd, "/", _dedupTotal,
                      " processed, ", Length(all_fpf) - before, " new, GC done\n");
                # Mid-combo checkpoint: save only NEW groups since last chunk save
                if ckptLogFile <> "" and Length(all_fpf) > _lastCkptPos then
                    _AppendCheckpointDelta(ckptLogFile,
                        Concatenation("_dedup_partial_", String(_chunkEnd)),
                        all_fpf{[_lastCkptPos+1..Length(all_fpf)]},
                        totalCandidates, addedCount, Length(all_fpf),
                        allInvKeys{[_lastCkptPos+1..Length(allInvKeys)]});
                    _lastCkptPos := Length(all_fpf);
                    Print("      [dedup chunk] mid-combo checkpoint saved\n");
                fi;
            fi;
            _chunkStart := _chunkEnd + 1;
        od;
        Print("    combo: ", Length(newResults), " candidates -> ",
              Length(all_fpf) - before, " new (", Length(all_fpf), " total)\n");
    end;

    # Enumerate all combinations
    IterateCombinations := function(depth, currentFactors)
        local T, shifted, offs, off, k, P, c2Result, nonC2Len, allC2, liftResult,
              cacheKey, cachedResult, canUseC2Opt, _saved_boe, _combo_result,
              _normKey, _combo_succeeded, _preComboCandidates, _comboStartTime;

        if depth > Length(transitiveLists) then
            # Check cache first
            cacheKey := ComputeCacheKey(currentFactors);
            comboCount := comboCount + 1;

            # Checkpoint skip: if this combo was already completed, skip it
            if IsBound(completedKeySet.(cacheKey)) then
                Print("    >> combo [", cacheKey, "] CHECKPOINT SKIP\n");
                return;
            fi;

            Print("    >> combo [", cacheKey, "] factors=",
                  List(currentFactors, f -> [NrMovedPoints(f), TransitiveIdentification(f)]),
                  " |P|=", Product(List(currentFactors, Size)), "\n");
            fpfBeforeCombo := Length(all_fpf);
            _combo_succeeded := true;  # assume success; set false on failure
            _preComboCandidates := totalCandidates;
            _comboStartTime := Runtime();

            # Per-combo normalizer: use N_{S_{d_k}}(T_k) products + block swaps
            # instead of the full partition normalizer.
            if usePerComboNorm then
                _normKey := cacheKey;
                if IsBound(comboNormCache.(_normKey)) then
                    currentN := comboNormCache.(_normKey);
                else
                    currentN := BuildPerComboNormalizer(partition, currentFactors, n);
                    comboNormCache.(_normKey) := currentN;
                    Print("    per-combo |N| = ", Size(currentN),
                          " (vs full |N| = ", Size(N), ")\n");
                fi;
            fi;

            if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
                # Cache hit - use cached results (need to shift appropriately)
                cachedResult := FPF_SUBDIRECT_CACHE.(cacheKey);
                # Note: cached results are for a canonical shifting,
                # but since we deduplicate under normalizer, this is fine
                incrementalDedup(cachedResult);
            else
                # Wrap entire combo computation in error-safe handler.
                # GAP's NaturalHomomorphismByNormalSubgroup can trigger internal
                # bugs (ChangeSeriesThrough list index, etc.) for large groups
                # like TransitiveGroup(14,53/54). Catching errors at the
                # individual call level is insufficient because GAP internal
                # state gets corrupted. Instead, catch at the combo level.
                _saved_boe := BreakOnError;
                BreakOnError := false;
                _combo_result := CALL_WITH_CATCH(function()
                    local _shifted, _offs, _off, _k, _allC2, _nonC2Len,
                          _canUseC2Opt, _c2Result, _P, _liftResult;

                    _shifted := [];
                    _offs := [];
                    _off := 0;

                    for _k in [1..Length(currentFactors)] do
                        Add(_offs, _off);
                        Add(_shifted, ShiftGroup(currentFactors[_k], _off));
                        _off := _off + NrMovedPoints(currentFactors[_k]);
                    od;

                    if Length(_shifted) = 1 then
                        FPF_SUBDIRECT_CACHE.(cacheKey) := [_shifted[1]];
                        incrementalDedup([_shifted[1]]);
                    else
                        _allC2 := true;
                        _nonC2Len := Length(partition) - numTrailing2s;
                        for _k in [_nonC2Len + 1..Length(currentFactors)] do
                            if Size(currentFactors[_k]) <> 2 then
                                _allC2 := false;
                                break;
                            fi;
                        od;

                        if useC2Opt and _allC2 then
                            _canUseC2Opt := true;
                            for _k in [1.._nonC2Len] do
                                if not HasSmallAbelianization(currentFactors[_k]) then
                                    _canUseC2Opt := false;
                                    break;
                                fi;
                            od;

                            if _canUseC2Opt then
                                _c2Result := FindSubdirectsForPartitionWith2s(
                                    partition, currentFactors, _shifted, _offs);
                                if _c2Result <> fail then
                                    if Length(_c2Result) <= MAX_CACHE_RESULTS then
                                        FPF_SUBDIRECT_CACHE.(cacheKey) := _c2Result;
                                    else
                                        Print("    SKIP CACHE: ", Length(_c2Result), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                    fi;
                                    incrementalDedup(_c2Result);
                                else
                                    _P := Group(Concatenation(List(_shifted, GeneratorsOfGroup)));
                                    _liftResult := FindFPFClassesByLifting(_P, _shifted, _offs, N);
                                    if Length(_liftResult) <= MAX_CACHE_RESULTS then
                                        FPF_SUBDIRECT_CACHE.(cacheKey) := _liftResult;
                                    else
                                        Print("    SKIP CACHE: ", Length(_liftResult), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                    fi;
                                    incrementalDedup(_liftResult);
                                fi;
                            else
                                _P := Group(Concatenation(List(_shifted, GeneratorsOfGroup)));
                                _liftResult := FindFPFClassesByLifting(_P, _shifted, _offs, N);
                                if Length(_liftResult) <= MAX_CACHE_RESULTS then
                                    FPF_SUBDIRECT_CACHE.(cacheKey) := _liftResult;
                                else
                                    Print("    SKIP CACHE: ", Length(_liftResult), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                fi;
                                incrementalDedup(_liftResult);
                            fi;
                        else
                            if ShouldUseGeneralizedC2(_shifted) then
                                _c2Result := FindSubdirectsViaGeneralizedC2(currentFactors, _shifted, _offs);
                                if _c2Result <> fail and Length(_c2Result) > 0 then
                                    if Length(_c2Result) <= MAX_CACHE_RESULTS then
                                        FPF_SUBDIRECT_CACHE.(cacheKey) := _c2Result;
                                    else
                                        Print("    SKIP CACHE: ", Length(_c2Result), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                    fi;
                                    incrementalDedup(_c2Result);
                                else
                                    _P := Group(Concatenation(List(_shifted, GeneratorsOfGroup)));
                                    _liftResult := FindFPFClassesByLifting(_P, _shifted, _offs, N);
                                    if Length(_liftResult) <= MAX_CACHE_RESULTS then
                                        FPF_SUBDIRECT_CACHE.(cacheKey) := _liftResult;
                                    else
                                        Print("    SKIP CACHE: ", Length(_liftResult), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                    fi;
                                    incrementalDedup(_liftResult);
                                fi;
                            else
                                _P := Group(Concatenation(List(_shifted, GeneratorsOfGroup)));
                                _liftResult := FindFPFClassesByLifting(_P, _shifted, _offs, N);
                                if Length(_liftResult) <= MAX_CACHE_RESULTS then
                                    FPF_SUBDIRECT_CACHE.(cacheKey) := _liftResult;
                                else
                                    Print("    SKIP CACHE: ", Length(_liftResult), " results (> ", MAX_CACHE_RESULTS, ")\n");
                                fi;
                                incrementalDedup(_liftResult);
                            fi;
                        fi;
                    fi;
                    return true;
                end, []);
                BreakOnError := _saved_boe;
                if _combo_result[1] <> true then
                    Print("    FATAL: combo FAILED (GAP internal error)\n");
                    Print("    combo key: ", cacheKey, "\n");
                    Print("    partial contribution: ", Length(all_fpf) - fpfBeforeCombo,
                          " groups added before failure\n");
                    Print("    Crashing so process can be resumed from checkpoint.\n");
                    # Save checkpoint of everything BEFORE this failed combo
                    if ckptLogFile <> "" then
                        Print("    Saving pre-failure checkpoint (",
                              Length(completedKeyList), " combos, ",
                              Length(all_fpf), " groups)...\n");
                    fi;
                    Error("Combo failed: ", cacheKey, " - resume from checkpoint");
                fi;
            fi;

            # Per-combo timing log
            Print("    combo #", comboCount, " done (",
                  (Runtime() - startTime) / 1000.0, "s elapsed, ",
                  Length(all_fpf), " fpf total)\n");

            # Per-combo output: write combo results to separate file
            if COMBO_OUTPUT_DIR <> "" then
                _WriteComboResults(COMBO_OUTPUT_DIR, cacheKey,
                    all_fpf{[fpfBeforeCombo+1..Length(all_fpf)]},
                    totalCandidates - _preComboCandidates,
                    Runtime() - _comboStartTime);
            fi;

            # Checkpoint save: record this combo as completed
            # Only if it succeeded (failed combos should be retried on resume)
            if _combo_succeeded then
                Add(completedKeyList, cacheKey);
                completedKeySet.(cacheKey) := true;
                # Clean up any _dedup_partial_ keys from mid-combo checkpoints.
                # The full combo is now complete, so partial markers are stale.
                completedKeyList := Filtered(completedKeyList,
                    k -> Length(k) < 15 or k{[1..15]} <> "_dedup_partial_");
                # Append-based checkpoint: only write the NEW groups from this combo
                if ckptLogFile <> "" then
                    _AppendCheckpointDelta(ckptLogFile, cacheKey,
                        all_fpf{[fpfBeforeCombo+1..Length(all_fpf)]},
                        totalCandidates, addedCount, Length(all_fpf),
                        allInvKeys{[fpfBeforeCombo+1..Length(allInvKeys)]});
                    lastCkptTime := Runtime();
                    Print("    CHECKPOINT SAVED (",
                          Length(completedKeyList), " combos, ",
                          Length(all_fpf), " groups)\n");
                fi;
            else
                Print("    SKIPPING checkpoint for failed combo (will retry on resume)\n");
            fi;

            # Heartbeat update (written every combo; overhead negligible)
            if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
                PrintTo(_HEARTBEAT_FILE, "alive ",
                        Int(Runtime() / 1000), "s combo #",
                        comboCount, " fpf=", Length(all_fpf), "\n");
            fi;

            return;
        fi;

        for T in transitiveLists[depth] do
            # Skip redundant orderings for equal-degree parts.
            # ComputeCacheKey sorts factor IDs, so (A4,D4) and (D4,A4)
            # map to the same key. Only visit non-decreasing order.
            if depth > 1 and partition[depth] = partition[depth-1] then
                if TransitiveIdentification(T) <
                   TransitiveIdentification(currentFactors[depth-1]) then
                    continue;
                fi;
            fi;
            Add(currentFactors, T);
            IterateCombinations(depth + 1, currentFactors);
            Remove(currentFactors);
        od;
    end;

    IterateCombinations(1, []);

    # Final checkpoint: write monolithic .g file for archival
    if ckptFile <> "" then
        _SaveCheckpoint(ckptFile, completedKeyList, all_fpf,
                        totalCandidates, addedCount, allInvKeys);
        AppendTo(ckptFile, "\n_CKPT_RICH_INV := ", _richInvActive, ";\n");
        if ckptLogFile <> "" and IsExistingFile(ckptLogFile) then
            _BackupFile(ckptLogFile);
            PrintTo(ckptLogFile, "# Merged into .g checkpoint\n");
        fi;
        Print("  FINAL CHECKPOINT SAVED (",
              Length(completedKeyList), " combos, ",
              Length(all_fpf), " groups)\n");
    fi;

    Print("  |N| = ", Size(N), " (vs |S_", n, "| = ", Factorial(n), ")\n");
    Print("  Speedup factor: ", Int(Factorial(n) / Size(N)), "x\n");
    Print("  Final count: ", Length(all_fpf), " (from ", totalCandidates, " candidates)\n");
    Print("  Time: ", (Runtime() - startTime) / 1000.0, "s\n");

    return all_fpf;
end;

###############################################################################
# Main S_n computation
###############################################################################

CountAllConjugacyClassesFast := function(n)
    local partitions, total, part, fpf_classes, startTime, prev;

    if IsBound(LIFT_CACHE.(String(n))) then
        Print("S_", n, " from cache: ", LIFT_CACHE.(String(n)), "\n");
        return LIFT_CACHE.(String(n));
    fi;

    startTime := Runtime();
    InitLog(n);

    # Reset H^1 timing statistics for fresh measurement
    if IsBound(ResetH1TimingStats) then
        ResetH1TimingStats();
    fi;

    Print("Computing S_", n, "\n");
    Print("==========================================\n\n");

    if n = 1 then
        LIFT_CACHE.("1") := 1;
        return 1;
    fi;

    prev := CountAllConjugacyClassesFast(n - 1);
    Print("\nInherited from S_", n-1, ": ", prev, "\n\n");
    LogMsg(Concatenation("Inherited from S_", String(n-1), ": ", String(prev)));

    total := prev;

    partitions := PartitionsMinPart(n, 2);
    Print("Processing ", Length(partitions), " partitions...\n\n");

    for part in partitions do
        Print("Partition ", part, ":\n");
        fpf_classes := FindFPFClassesForPartition(n, part);
        Print("  => ", Length(fpf_classes), " classes\n\n");
        LogMsg(Concatenation("Partition ", String(part), ": ", String(Length(fpf_classes))));
        total := total + Length(fpf_classes);
    od;

    Print("==========================================\n");
    Print("Total S_", n, ": ", total, "\n");
    Print("Time: ", (Runtime() - startTime) / 1000.0, "s\n");

    # Print H^1 timing statistics if available
    if IsBound(PrintH1TimingStats) then
        PrintH1TimingStats();
    fi;

    LogMsg(Concatenation("FINAL S_", String(n), ": ", String(total)));
    LIFT_CACHE.(String(n)) := total;

    # Save FPF cache to database for future runs
    if IsBound(SaveFPFSubdirectCache) then
        SaveFPFSubdirectCache();
    fi;

    return total;
end;

###############################################################################
# Testing
###############################################################################

CountDirect := function(n)
    return Length(ConjugacyClassesSubgroups(SymmetricGroup(n)));
end;

TestFast := function()
    local known, n, computed, expected;

    known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

    Print("Testing fast v2 algorithm:\n");
    Print("==========================\n\n");

    for n in [2..8] do
        expected := known[n];
        Print("S_", n, " (expected ", expected, "): ");
        computed := CountAllConjugacyClassesFast(n);
        if computed = expected then
            Print("OK\n\n");
        else
            Print("FAIL (got ", computed, ")\n\n");
        fi;
    od;
end;

###############################################################################

Print("Lifting Method FAST V2 loaded.\n");
Print("===============================\n");
Print("Uses: Chief series lifting + Normalizer deduplication\n");
Print("\nMain: CountAllConjugacyClassesFast(n)\n");
Print("Test: TestFast()\n\n");
