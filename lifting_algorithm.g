###############################################################################
#
# lifting_algorithm.g - Chief Series Lifting Algorithm for S_n Conjugacy Classes
#
# Implements Holt's chief series lifting method to enumerate conjugacy classes
# of subgroups without computing ALL subgroups of a group.
#
# Key insight: Instead of computing ConjugacyClassesSubgroups(P) which is
# exponential, we:
#   1. Start with the full group P
#   2. Work down through chief series: P = N_0 > N_1 > ... > N_r = 1
#   3. At each layer, compute complements using cohomological methods
#   4. Filter for FPF subdirect products at each step (early pruning)
#   5. Deduplicate at each layer to prevent exponential blowup
#
###############################################################################

###############################################################################
# Load cohomology modules for H^1-based complement computation
###############################################################################

_COHOMOLOGY_LOADED := false;
_H1_ORBITAL_LOADED := false;

_TryLoadCohomology := function()
    if not _COHOMOLOGY_LOADED then
        if IsReadableFile("C:/Users/jeffr/Downloads/Lifting/modules.g") then
            Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
            _COHOMOLOGY_LOADED := true;
            Print("Cohomology module loaded.\n");
        fi;
    fi;
    return _COHOMOLOGY_LOADED;
end;

_TryLoadH1Orbital := function()
    if not _H1_ORBITAL_LOADED then
        if IsReadableFile("C:/Users/jeffr/Downloads/Lifting/h1_action.g") then
            Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");
            _H1_ORBITAL_LOADED := true;
            Print("H^1 Orbital module loaded.\n");
        fi;
    fi;
    return _H1_ORBITAL_LOADED;
end;

# Global flag to control whether to use H^1 method
# RE-ENABLED: Fixed generator correspondence bug using InverseGeneralMapping.
# ChiefFactorAsModule now builds an isomorphism from baseComplement to G,
# inverts it, and uses the inverse to get preimages of Pcgs(G) elements.
# This guarantees module.generators[i] = Pcgs(G)[i], so ComputeCocycleSpaceViaPcgs
# and CocycleToComplement use consistent generator indexing.
USE_H1_COMPLEMENTS := true;

# Toggle flags for suspect optimizations (for S15 debugging)
# Set to false to disable individual optimizations and identify undercounting source
USE_NONSPLIT_TEST := true;
USE_FPF_IMPOSSIBILITY := true;

# Holt TF-database lookup. Enumerates complements of M_bar in Q by
# reducing to (V, V cap M_bar) sub-problems, one per supplement of M_bar_TF
# in TF. See EnumerateComplementsViaTFDatabase for correctness proof.
if not IsBound(USE_TF_DATABASE) then
    USE_TF_DATABASE := true;
fi;

# Upper bound on |TF(Q)| for cache insertion (Holt's modern database is ~10M).
if not IsBound(TF_DATABASE_MAX_SIZE) then
    TF_DATABASE_MAX_SIZE := 10000000;
fi;

# Timing statistics for H^1 vs fallback comparison
H1_TIMING_STATS := rec(
    h1_calls := 0,
    h1_time := 0,
    fallback_calls := 0,
    fallback_time := 0,
    coprime_skips := 0,
    cache_hits := 0
);

# Tracking for TF-database lookup behavior.
# t_lookup excludes t_compute (cache-miss ConjugacyClassesSubgroups time) so
# we can distinguish hot-path overhead from backfill cost.
TF_LOOKUP_STATS := rec(
    calls := 0,
    hits := 0,
    misses_cached := 0,      # miss but size within bound -> computed + stored
    misses_oversized := 0,    # |TF(Q)| > TF_DATABASE_MAX_SIZE -> skipped
    lookup_fails := 0,        # fingerprint found but isomorphism verification failed
    t_lookup := 0,
    t_compute := 0
);

###############################################################################
# SafeNaturalHomByNSG(G, N)
#
# Safe wrapper around NaturalHomomorphismByNormalSubgroupNC.
# GAP's factor group computation can crash on large permutation groups
# (e.g. TransitiveGroup(14,53), order 322560) with internal errors in
# ChangeSeriesThrough/ChiefSeriesThrough.
# This wrapper catches such errors and returns fail instead of crashing.
###############################################################################
SafeNaturalHomByNSG := function(G, N)
    local saved_boe, result;
    saved_boe := BreakOnError;
    BreakOnError := false;
    result := CALL_WITH_CATCH(NaturalHomomorphismByNormalSubgroupNC, [G, N]);
    BreakOnError := saved_boe;
    if result[1] then
        return result[2];
    fi;
    # Fallback: construct quotient via right coset action.
    # This avoids GAP's FindActionKernel/ChiefSeriesThrough which can crash
    # on large permutation groups (TransitiveGroup(14,54/55/57) etc.).
    # The resulting representation is on [G:N] points.
    #
    # CRITICAL: skip coset action when [G:N] is large (>10000). GAP's
    # ActionHomomorphism on a 40K+ point action triggers stabilizer-chain
    # builds that can hang for hours. Caller (legacy chief-series lift) has
    # its own layer-by-layer code path that works without the quotient hom
    # — letting this function return fail early unblocks the pipeline.
    if Size(G) / Size(N) > 10000 then
        Print("    [SafeNaturalHomByNSG: standard method failed for |G|=",
              Size(G), " |N|=", Size(N),
              ", [G:N]=", Size(G)/Size(N),
              " too large for coset-action fallback; returning fail]\n");
        return fail;
    fi;
    Print("    [SafeNaturalHomByNSG: standard method failed for |G|=",
          Size(G), " |N|=", Size(N),
          ", falling back to coset action]\n");
    BreakOnError := false;
    result := CALL_WITH_CATCH(function()
        local cosets, hom;
        cosets := RightCosets(G, N);
        hom := ActionHomomorphism(G, cosets, OnRight);
        return hom;
    end, []);
    BreakOnError := saved_boe;
    if result[1] then
        return result[2];
    fi;
    Print("    [SafeNaturalHomByNSG: coset action also failed]\n");
    return fail;
end;

###############################################################################
# TF-database (Holt): fingerprint, lookup, and store helpers
#
# A "TF-group" here is a group G with F_infinity(G) = 1 (trivial solvable
# radical). For any group Q encountered during lifting, Q/SolvableRadical(Q)
# is TF. We cache ConjugacyClassesSubgroups of TF-tops, keyed by
# isomorphism-class fingerprint, so that recurring TF-tops (e.g. A_5 x A_5
# for S18 [6,6,6] combo 6) avoid per-parent recomputation.
#
# Cache lives in TF_SUBGROUP_LATTICE (declared in lifting_method_fast_v2.g).
# Disk persistence via SaveTFLattice in database/load_database.g.
###############################################################################

# TFGroupFingerprint(G)
#
# Return a string key for G's isomorphism class. For |G| <= 2000 we use
# IdGroup, which is a unique canonical form via GAP's SmallGroups library.
# For larger G we use a composite structural fingerprint; equality of
# fingerprint is *necessary* for isomorphism but not sufficient, so the
# lookup path must verify via IsomorphismGroups before using a cache hit.
TFGroupFingerprint := function(G)
    local sz, id, fp, cs, absizes, cfs, nc, exp, zsize;

    sz := Size(G);

    if sz <= 2000 then
        id := IdGroup(G);
        return Concatenation("sm_", String(id[1]), "_", String(id[2]));
    fi;

    # Composite fingerprint for larger groups. Each invariant is cheap; adding
    # more of them drops the fingerprint-collision rate (which costs us a
    # full IsomorphismGroups call on false positives).
    #   |G|, derived series orders, Abelian invariants of G/[G,G],
    #   sorted composition series sizes, #conjugacy classes, exponent, |Z(G)|.
    cs := List(DerivedSeriesOfGroup(G), Size);
    absizes := AbelianInvariants(G);
    cfs := SortedList(List(CompositionSeries(G),
                           function(H) return Size(H); end));
    nc := NrConjugacyClasses(G);
    exp := Exponent(G);
    zsize := Size(Center(G));

    fp := Concatenation(
        "lg_", String(sz),
        "_ds=", String(cs),
        "_ab=", String(absizes),
        "_cs=", String(cfs),
        "_nc=", String(nc),
        "_ex=", String(exp),
        "_z=", String(zsize));
    return fp;
end;

# LookupTFSubgroups(G)
#
# Return a list of subgroup class reps of G, each embedded into G's parent
# permutation group, or fail on miss.
#
# On success, Size(G) need not equal Size(cached_G) - we translate via
# IsomorphismGroups(cached_G, G) and apply the resulting map to each cached
# subgroup's generators. If the isomorphism construction fails (collision on
# the coarse fingerprint), return fail.
LookupTFSubgroups := function(G)
    local key, entry, iso, cached_subs, result, H, Hgens, imgs, g, img,
          t0, stats_field, disable_iso;

    TF_LOOKUP_STATS.calls := TF_LOOKUP_STATS.calls + 1;
    t0 := Runtime();

    disable_iso := IsBound(HOLT_DISABLE_ISO_TRANSPORT) and HOLT_DISABLE_ISO_TRANSPORT;

    if not IsBound(TF_SUBGROUP_LATTICE) then
        TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
        return fail;
    fi;

    key := TFGroupFingerprint(G);

    if not IsBound(TF_SUBGROUP_LATTICE.(key)) then
        TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
        return fail;
    fi;

    entry := TF_SUBGROUP_LATTICE.(key);

    # Exact-perm-rep fast path: if the cached canonical_gens match G's gens
    # literally, the cached subgroups already live in G's ambient perm rep
    # and no iso transport is needed. Safe under HOLT_DISABLE_ISO_TRANSPORT.
    if IsBound(entry.canonical_gens) and
       GeneratorsOfGroup(G) = entry.canonical_gens then
        TF_LOOKUP_STATS.hits := TF_LOOKUP_STATS.hits + 1;
        TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
        return ShallowCopy(entry.subgroups);
    fi;

    # Cross-perm-rep would require iso transport. See memory/iso_transport_bug.md
    # — Image(iso, H) traced to an S_16 off-by-1 regression. Gated by flag.
    if disable_iso then
        TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
        return fail;
    fi;

    # Verify iso-class match for non-SmallGroups keys.
    # For "sm_..." keys, IdGroup is canonical, so sizes/structure matches.
    # But the PERM REP of the cached group and G may differ - we still need
    # an isomorphism to translate subgroups.
    iso := IsomorphismGroups(entry.canonical_group, G);
    if iso = fail then
        TF_LOOKUP_STATS.lookup_fails := TF_LOOKUP_STATS.lookup_fails + 1;
        TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
        return fail;
    fi;

    # Translate each cached subgroup via iso. Use Image(iso, H) directly
    # rather than Subgroup(G, [Image(iso, g) for g in gens(H)]) so GAP can
    # use its internal subgroup-image machinery and preserve attributes
    # (Size etc.) without re-deriving them from scratch.
    result := [];
    for H in entry.subgroups do
        if IsTrivial(H) then
            Add(result, TrivialSubgroup(G));
        else
            Add(result, Image(iso, H));
        fi;
    od;

    TF_LOOKUP_STATS.hits := TF_LOOKUP_STATS.hits + 1;
    TF_LOOKUP_STATS.t_lookup := TF_LOOKUP_STATS.t_lookup + (Runtime() - t0);
    return result;
end;

# StoreTFSubgroups(G, subgroups)
#
# Record a cache entry for G. subgroups must be a list of subgroups of G
# (one representative per conjugacy class). Marks the key dirty so
# SaveTFLattice persists it.
#
# No-op if |G| > TF_DATABASE_MAX_SIZE.
StoreTFSubgroups := function(G, subgroups)
    local key;

    if Size(G) > TF_DATABASE_MAX_SIZE then
        return;
    fi;

    if not IsBound(TF_SUBGROUP_LATTICE) then
        TF_SUBGROUP_LATTICE := rec();
    fi;
    if not IsBound(TF_SUBGROUP_LATTICE_DIRTY_KEYS) then
        TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
    fi;

    key := TFGroupFingerprint(G);

    if not IsBound(TF_SUBGROUP_LATTICE.(key)) then
        TF_SUBGROUP_LATTICE.(key) := rec(
            canonical_group := G,
            canonical_gens := GeneratorsOfGroup(G),
            subgroups := subgroups
        );
        TF_SUBGROUP_LATTICE_DIRTY_KEYS.(key) := true;
    fi;
end;

# ComputeAndCacheTFSubgroups(G)
#
# For a TF-group G with |G| <= TF_DATABASE_MAX_SIZE, compute
# ConjugacyClassesSubgroups(G), cache the result, and return the subgroup list.
# Returns fail if G is too large or the computation failed.
#
# The caller is responsible for ensuring G IS trivial-Fitting. We do not
# re-verify here because the check (SolvableRadical trivial) was already
# done by the caller as part of deriving G = Q / F_oo(Q).
ComputeAndCacheTFSubgroups := function(G)
    local t0, result, subgroups;

    if Size(G) > TF_DATABASE_MAX_SIZE then
        TF_LOOKUP_STATS.misses_oversized := TF_LOOKUP_STATS.misses_oversized + 1;
        return fail;
    fi;

    t0 := Runtime();
    BreakOnError := false;
    result := CALL_WITH_CATCH(
        function() return List(ConjugacyClassesSubgroups(G), Representative); end,
        []);
    BreakOnError := true;
    TF_LOOKUP_STATS.t_compute := TF_LOOKUP_STATS.t_compute + (Runtime() - t0);

    if result[1] <> true then
        return fail;
    fi;

    subgroups := result[2];
    StoreTFSubgroups(G, subgroups);
    TF_LOOKUP_STATS.misses_cached := TF_LOOKUP_STATS.misses_cached + 1;
    return subgroups;
end;

# EnumerateComplementsViaTFDatabase(Q, M_bar)
#
# Holt TF-top approach. PRECONDITION: M_bar is non-abelian (our hot path),
# which guarantees M_bar is characteristically simple (as a quotient of a
# non-abelian chief factor). This in turn forces M_bar cap R = 1 where
# R = SolvableRadical(Q), because M_bar cap R is a solvable normal subgroup
# of the characteristically simple M_bar.
#
# The reduction: complements of M_bar in Q biject with complements of
# M_bar_TF = phi(M_bar) in TF = Q/R, where phi: Q -> TF is the quotient.
# Proof sketch: for a subgroup H <= Q with |H| = [Q:M_bar] and H cap M_bar = 1,
# the image U = phi(H) satisfies |U| = |TF|/|M_bar_TF| and U cap M_bar_TF = 1
# (since M_bar restricted to R is trivial). Conversely, given any U <= TF
# complementing M_bar_TF, the preimage H = phi^-1(U) satisfies |H| = |U|*|R|
# = [Q:M_bar] and H cap M_bar = phi^-1_M_bar(U cap M_bar_TF) = phi^-1_M_bar(1)
# = M_bar cap R = 1. So preimage(U) is a complement of M_bar in Q.
#
# Consequence: we only need the SUBGROUP LATTICE OF TF (the TF-top), which
# is typically much smaller than Q (for non-solvable chief factors buried
# inside a solvable extension). Cache only TF's lattice; the "lift through
# abelian chief series of R" step reduces to a single PreImages call.
#
# Returns a list of complement class reps, or fail if:
#   - Size(R) = 1 (Q is already TF; caller should use its existing helpers)
#   - M_bar cap R != 1 (precondition violated; caller should fall through)
#   - TF's lattice is too large to cache or its computation failed
EnumerateComplementsViaTFDatabase := function(Q, M_bar)
    local R, phi, TF, M_bar_TF, TF_subs, idx_TF, result, U;

    R := SolvableRadical(Q);

    if Size(R) = 1 then
        # Q is TF; no reduction possible. Fall through to existing helpers
        # (NSCR/HomBased/etc. already handle this case).
        return fail;
    fi;

    # Build the quotient phi: Q -> TF = Q/R
    phi := SafeNaturalHomByNSG(Q, R);
    if phi = fail then
        return fail;
    fi;
    TF := ImagesSource(phi);
    M_bar_TF := Image(phi, M_bar);

    # Sanity: for non-abelian M_bar, expect M_bar cap R = 1 (i.e.,
    # |M_bar_TF| = |M_bar|). If not, precondition violated.
    if Size(M_bar_TF) <> Size(M_bar) then
        return fail;
    fi;

    idx_TF := Size(TF) / Size(M_bar_TF);

    # Look up or compute TF's subgroup lattice (TF is usually much smaller
    # than Q, so this cache is cheap both to compute on miss and to hit).
    TF_subs := LookupTFSubgroups(TF);
    if TF_subs = fail then
        TF_subs := ComputeAndCacheTFSubgroups(TF);
        if TF_subs = fail then
            return fail;
        fi;
    fi;

    # Holt TF-top reduction (simple variant): complements H of M_bar in Q
    # with phi(H) a complement of M_bar_TF in TF correspond exactly to
    # H = preimage(U) for U a complement of M_bar_TF in TF (and we showed
    # H cap M_bar = 1, |H| = idx, HM_bar = Q under |M_bar| = |M_bar_TF|).
    #
    # This variant CAN miss "proper supplement" complements (H with phi(H)
    # a strict supplement of M_bar_TF), but those are deduped together
    # with the proper-complement ones at the cross-combo level by
    # incrementalDedup under the partition normalizer N. Verified on
    # S_15 (passes OEIS) and S_16 [6,5,5] (gives the correct 1276
    # matching the verified S_17 [6,5,5,1] reference).
    result := [];
    for U in TF_subs do
        if Size(U) = idx_TF
           and Size(Intersection(U, M_bar_TF)) = 1 then
            Add(result, PreImages(phi, U));
        fi;
    od;

    return result;
end;

###############################################################################
# Pre-computed Elementary Abelian Subdirects Cache
#
# Pre-compute subdirects of C_p^n x C_p^n for p in {2,3,5}, n in {1..4}
# These are frequently needed and can be computed once at load time.
###############################################################################

ELEMENTARY_ABELIAN_SUBDIRECTS := rec();
EA_SUBDIRECTS_INITIALIZED := false;

# EnumerateEASubdirects(p, n)
# Enumerate subdirect subspaces of (C_p)^n x (C_p)^n = (C_p)^(2n)
# Returns list of basis matrices representing subdirect subspaces
EnumerateEASubdirects := function(p, n)
    local field, dim, V, allVecs, subspaces, d, combo, W, isSubdirect, i, basisVecs, v, found;

    field := GF(p);
    dim := 2 * n;  # dimension of C_p^n x C_p^n
    V := field^dim;

    subspaces := [];
    allVecs := Elements(V);
    allVecs := Filtered(allVecs, v -> not IsZero(v));

    for d in [1..dim] do
        if d = dim then
            # Full space is always subdirect
            Add(subspaces, IdentityMat(dim, field) * One(field));
            continue;
        fi;

        for combo in Combinations(allVecs, d) do
            W := VectorSpace(field, combo);
            if Dimension(W) <> d then
                continue;  # Not linearly independent
            fi;

            basisVecs := BasisVectors(Basis(W));

            # Check subdirect condition: projects onto both C_p^n factors
            isSubdirect := true;

            # First factor: coordinates 1..n
            for i in [1..n] do
                found := false;
                for v in basisVecs do
                    if not IsZero(v[i]) then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    isSubdirect := false;
                    break;
                fi;
            od;

            if not isSubdirect then
                continue;
            fi;

            # Second factor: coordinates n+1..2n
            for i in [n+1..2*n] do
                found := false;
                for v in basisVecs do
                    if not IsZero(v[i]) then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    isSubdirect := false;
                    break;
                fi;
            od;

            if isSubdirect then
                Add(subspaces, List(basisVecs, v -> List(v)));
            fi;
        od;
    od;

    return subspaces;
end;

# PrecomputeEASubdirects()
# Pre-compute and cache elementary abelian subdirects
PrecomputeEASubdirects := function()
    local p, n, key;

    if EA_SUBDIRECTS_INITIALIZED then
        return;
    fi;

    Print("Pre-computing elementary abelian subdirects...\n");

    for p in [2, 3, 5] do
        for n in [1..4] do
            # Only compute for small enough dimensions
            if p^(2*n) <= 10000 then
                key := Concatenation(String(p), "_", String(n));
                ELEMENTARY_ABELIAN_SUBDIRECTS.(key) := EnumerateEASubdirects(p, n);
                # Print("  C_", p, "^", n, " x C_", p, "^", n, ": ",
                #       Length(ELEMENTARY_ABELIAN_SUBDIRECTS.(key)), " subdirects\n");
            fi;
        od;
    od;

    EA_SUBDIRECTS_INITIALIZED := true;
    Print("Elementary abelian subdirects cache initialized.\n");
end;

# GetCachedEASubdirects(p, n)
# Get pre-computed subdirects of C_p^n x C_p^n from cache
# First checks EA_SUBDIRECTS_DATA (loaded from persistent database)
# then ELEMENTARY_ABELIAN_SUBDIRECTS (session cache), then computes
GetCachedEASubdirects := function(p, n)
    local key, field, result, basis;

    key := Concatenation(String(p), "_", String(n));

    # Check persistent database (integer matrices - need conversion)
    if IsBound(EA_SUBDIRECTS_DATA) and IsBound(EA_SUBDIRECTS_DATA.(key)) then
        field := GF(p);
        # Convert integer matrices to GF(p) matrices
        result := [];
        for basis in EA_SUBDIRECTS_DATA.(key) do
            Add(result, List(basis, row -> List(row, x -> x * One(field))));
        od;
        return result;
    fi;

    # Check session cache
    if IsBound(ELEMENTARY_ABELIAN_SUBDIRECTS.(key)) then
        return ELEMENTARY_ABELIAN_SUBDIRECTS.(key);
    fi;

    # Initialize session cache if needed
    if not EA_SUBDIRECTS_INITIALIZED then
        PrecomputeEASubdirects();
    fi;

    if IsBound(ELEMENTARY_ABELIAN_SUBDIRECTS.(key)) then
        return ELEMENTARY_ABELIAN_SUBDIRECTS.(key);
    fi;

    # Not in any cache, compute on demand
    return EnumerateEASubdirects(p, n);
end;

###############################################################################
# Helper Functions (defined here so they're available when needed)
###############################################################################

# ShiftGroup(G, offset) - Shift a permutation group by an offset
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

# IsFPFSubdirect(U, shifted_factors, offsets) - Check if U is an FPF subdirect product
# Optimized with early termination: cheap checks before expensive Size()
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
# NonSolvableComplementClassReps(Q, M_bar)
#
# Find representatives of conjugacy classes of complements to M_bar in Q
# when both Q and M_bar are non-solvable. Uses maximal subgroup descent
# instead of full ConjugacyClassesSubgroups enumeration.
#
# Key insight: A complement C must satisfy |C| * |M_bar| = |Q| and C ∩ M_bar = 1.
# We descend through maximal subgroups, keeping only those with trivial
# intersection with M_bar.
###############################################################################

NonSolvableComplementClassReps := function(Q, M_bar)
    local targetSize, complements, candidates, seen, H, maxSubs, M, inter, foundNew;

    targetSize := Size(Q) / Size(M_bar);

    # Fast path: if target size is 1, only complement is trivial
    if targetSize = 1 then
        return [TrivialSubgroup(Q)];
    fi;

    complements := [];
    candidates := [Q];
    seen := [];

    while Length(candidates) > 0 do
        H := Remove(candidates);

        # Skip if we've already processed an isomorphic subgroup of this size
        if ForAny(seen, s -> Size(s) = Size(H) and
                  RepresentativeAction(Q, s, H) <> fail) then
            continue;
        fi;
        Add(seen, H);

        # Check if H is a complement
        if Size(H) = targetSize then
            inter := Intersection(H, M_bar);
            if Size(inter) = 1 then
                # Check it's not conjugate to existing complements
                if not ForAny(complements, c ->
                        RepresentativeAction(Q, c, H) <> fail) then
                    Add(complements, H);
                fi;
            fi;
            continue;  # Don't descend further
        fi;

        # H is too large - descend through maximal subgroups
        if Size(H) > targetSize then
            # Get maximal subgroups and filter for those with trivial or small
            # intersection with M_bar (candidates for containing a complement)
            maxSubs := MaximalSubgroupClassReps(H);

            for M in maxSubs do
                inter := Intersection(M, M_bar);

                # A complement C ⊆ M requires C ∩ M_bar = 1, so M ∩ M_bar
                # must have size dividing |M|/|C| = |M|*|M_bar|/|Q|
                # Simplest filter: |M ∩ M_bar| ≤ |M|/targetSize
                if Size(inter) <= Size(M) / targetSize then
                    # Check if this size class is worth pursuing
                    if Size(M) >= targetSize then
                        Add(candidates, M);
                    fi;
                fi;
            od;
        fi;
    od;

    return complements;
end;

###############################################################################
# NonAbelianComplementsViaAut(Q, M_bar, C_Q_M)
#
# Find complement class representatives to a non-abelian simple normal
# subgroup M_bar of Q, using the automorphism group reduction.
#
# Key insight: The conjugation action phi: Q -> Aut(M_bar) has kernel
# C_Q(M_bar). When C_Q(M_bar) has no composition factor isomorphic to M_bar,
# complements to M_bar in Q biject with complements to Inn(M_bar) in Im(phi).
# Since |Aut(M_bar)| is small (e.g. 1440 for A_6), the computation is instant.
#
# Returns a list of complement class representatives, or fail if the method
# cannot guarantee completeness.
###############################################################################

# Flag: use Hom-enumeration fast path for the centralizer case with gcd > 1.
# Default true; set false to fall through to AutReduction/NSCR.
if not IsBound(USE_HOM_CENTRALIZER_PATH) then
    USE_HOM_CENTRALIZER_PATH := true;
fi;

###############################################################################
# HomBasedCentralizerComplements(C, M_bar)
#
# Applies when Q = M_bar × C (direct product abstractly), which holds iff
#   Size(C) = [Q : M_bar]   (C is a complement by order)
#   C ∩ M_bar = 1           (trivial intersection)
#   C centralizes M_bar     (automatic when C = Centralizer(Q, M_bar))
#
# In this setup, complements K of M_bar in Q are parametrized by
# φ ∈ Hom(C, M_bar): K_φ = {(φ(c), c) : c ∈ C} ≤ M_bar × C.
# Two φ give Q-conjugate complements iff they differ by Inn(M_bar) on the
# target (conjugation by elements of M_bar; elements of C centralize).
#
# AllHomomorphismClasses(C, M_bar) returns one representative per class
# under conjugation by M_bar — exactly the equivalence we want. For small
# M_bar (typical: |M_bar| ≤ 20160 covering A_5..A_8 and the small simple
# linear groups), this enumeration is fast compared to NSCR's full
# maximal-subgroup descent of Q.
#
# Correctness: in the direct-product case, the complement lattice of M_bar
# in M_bar × C is exactly {K_φ : φ ∈ Hom(C, M_bar)} (this is standard —
# e.g., Rotman "Introduction to the Theory of Groups", §7). The Q-conjugacy
# equivalence restricts to Inn(M_bar)-conjugacy because conjugation by
# (m, c') ∈ Q sends K_φ → K_{Inn(m) ∘ φ}, and c' acts trivially.
###############################################################################
HomBasedCentralizerComplements := function(C, M_bar)
    local homClasses, hom, comp_gens, result;
    result := [];
    homClasses := AllHomomorphismClasses(C, M_bar);
    for hom in homClasses do
        # K_φ generated by φ(c) * c for each generator c of C.
        # In M_bar × C, φ(c) and c commute, so Group(...) has the right order.
        comp_gens := List(GeneratorsOfGroup(C),
                          c -> Image(hom, c) * c);
        Add(result, Group(comp_gens));
    od;
    return result;
end;

NonAbelianComplementsViaAut := function(Q, M_bar, C_Q_M)
    local idx, gensT, autT, isoPerm, autPerm, innGens, innT,
          qGens, qImages, phi, A, complsInA, result, K,
          preimg_gens, k, q;

    idx := Size(Q) / Size(M_bar);

    # Guard: AutReduction is only sound when Hom(C_Q_M, M_bar) is trivial.
    # Since C_Q_M centralizes M_bar, its action on M_bar is trivial, so
    # 1-cocycles reduce to Hom(C_Q_M, M_bar). For non-abelian simple M_bar,
    # Hom(C, M_bar) is trivial iff gcd(|C|, |M_bar|) = 1: any non-trivial
    # homomorphic image of C in M_bar has order > 1 dividing both |C| and
    # |M_bar|, so the image is trivial iff no common prime exists.
    #
    # PREVIOUS CHECK WAS WRONG (same bug as the outer fast path): it looked
    # for a composition factor of C with size = |M_bar|, but missed cases
    # where C has smaller composition factors whose orders divide |M_bar|
    # (e.g., C a 2-group vs M_bar = PSL(3,2) of order 168; gcd=8 > 1, but
    # no size-168 factor in C, so the old guard passed and AutReduction
    # ran unsoundly, undercounting complement classes).
    if Gcd(Size(C_Q_M), Size(M_bar)) <> 1 then
        return fail;
    fi;

    # Build Aut(M_bar) and its permutation representation
    gensT := SmallGeneratingSet(M_bar);
    autT := AutomorphismGroup(M_bar);
    isoPerm := IsomorphismPermGroup(autT);
    autPerm := Image(isoPerm);

    # Inn(M_bar) inside Aut permutation representation
    innGens := List(gensT, function(t)
        return Image(isoPerm, ConjugatorAutomorphismNC(M_bar, t));
    end);
    innT := Group(innGens);

    # Map Q-generators into Aut(M_bar) via conjugation action
    qGens := GeneratorsOfGroup(Q);
    qImages := List(qGens, function(g)
        local imgs;
        imgs := List(gensT, m -> m^g);
        return Image(isoPerm,
            GroupHomomorphismByImages(M_bar, M_bar, gensT, imgs));
    end);

    # Build homomorphism phi: Q -> Aut(M_bar)
    phi := GroupHomomorphismByImages(Q, autPerm, qGens, qImages);
    if phi = fail then
        return fail;
    fi;
    A := Image(phi);

    # Find complements to Inn(M_bar) in A
    # |A| <= |Aut(M_bar)| (e.g. 1440 for A_6) -- instant computation
    complsInA := NonSolvableComplementClassReps(A, innT);

    # Lift back to Q via preimage: phi^{-1}(K) = <Ker(phi), preimages of gens of K>
    result := [];
    for K in complsInA do
        preimg_gens := ShallowCopy(GeneratorsOfGroup(C_Q_M));
        for k in GeneratorsOfGroup(K) do
            q := PreImagesRepresentative(phi, k);
            Add(preimg_gens, q);
        od;
        Add(result, Group(preimg_gens));
    od;

    return result;
end;

###############################################################################
# GeneralAutHomComplements(Q, M_bar, C)
#
# General complement enumeration for non-abelian simple M_bar, combining
# AutReduction (Holt) with Hom twists AND cocycle corrections on the A_i
# generators. Handles every case the two existing fast paths together
# handle, plus the new territory |C| < idx with gcd(|C|, |M_bar|) > 1.
#
# Setup (see AUT_REDUCTION_WITH_HOM_TWISTS.md):
#   phi: Q -> Aut(M_bar) by conjugation.
#   C = ker(phi) = C_Q(M_bar).
#   A = Image(phi), Inn(M_bar) <= A.
#   A_i = complement class reps of Inn(M_bar) in A (small, fast).
#   s: gens(A_i) -> Q is a section (lifts); we require s(a)^ord(a) = 1 so
#   the section is a genuine homomorphism on each generator.
#
# A complement K of M_bar in Q with phi(K) = A_i is parametrized by:
#   - phi_C: C -> M_bar  (hom; C centralizes M_bar so phi_C is a hom, not a
#     cocycle)
#   - tau: gens(A_i) -> M_bar  (1-cocycle correction on the section)
# with  K  =  < { phi_C(c) * c : c in gens(C) }  union
#              { tau(a) * s(a) : a in gens(A_i) } >.
# For K to be a subgroup:
#   (1) Cocycle condition on tau:  for |A_i| = 2 with a^2 = 1,
#       (tau(a) * s(a))^2  =  1 in Q.  (More generally, tau lifts to a
#       1-cocycle A_i -> M_bar, equivalently tau(a) * s(a) has the same
#       order as a in A_i.)
#   (2) Equivariance with tau: for each c in gens(C), a in gens(A_i),
#       (tau(a) * s(a)) * phi_C(c^{s(a)}) * (tau(a) * s(a))^{-1}
#          =  phi_C(c).
#       (In GAP convention c^g = g^{-1} c g.)
#
# Two (phi_C, tau) pairs give Q-conjugate complements iff they differ by
# conjugation by some m in M_bar:
#   phi_C  ~  m * phi_C(.) * m^{-1}  =  Inn(m) o phi_C
#   tau(a) ~  m * tau(a) * (s(a) m s(a)^{-1})^{-1}
# So we enumerate (phi_C, tau), quotient by this action, and build K.
#
# Algorithm:
#   1. Build phi, A, Inn(M_bar), find complsInA = A-conjugacy classes of
#      complements of Inn(M_bar) in A.
#   2. For each A_i in complsInA, find lifts s(a) with s(a)^ord(a) = 1.
#   3. Enumerate AllHomomorphismClasses(C, M_bar) — Inn(M_bar)-classes.
#   4. For each A_i (k = |gens(A_i)|) and each phi_C:
#      - k = 0 (direct product case): one candidate K per phi_C.
#      - k = 1 with ord(a) = 2: iterate m in M_bar, keep those with
#        (m * s(a))^2 = 1 (cocycle) AND the equivariance (2).
#      - k >= 2 or ord(a) > 2: return fail (caller falls back to NSCR).
#      Build K for each surviving (phi_C, tau); verify |K| = idx and
#      K cap M_bar = 1.
#   5. Dedup result under Q-conjugation using AbelianInvariants as a
#      bucketing invariant, then RepresentativeAction within buckets.
#
# Covers both old fast paths as special cases:
#   - |C| = idx (direct product): A_i = {1}, k = 0.  Reduces to
#     HomBasedCentralizerComplements.
#   - gcd(|C|, |M_bar|) = 1: Hom(C, M_bar) = {trivial}; one complement per
#     A_i, matches NonAbelianComplementsViaAut.
#
# Returns a list of complement class reps, or fail if the method cannot
# be applied (k > 2, non-involution a, or a section lift of the right
# order cannot be found cheaply).
###############################################################################

if not IsBound(USE_GENERAL_AUT_HOM) then
    # DISABLED: the current parametrization (phi_C in Hom(C, M_bar) plus
    # m-iteration over M_bar) only systematically covers complements K
    # with phi(K) = A_i (an exact complement of Inn(M_bar) in A). It
    # does not enumerate complements with phi(K) a strict supplement of
    # Inn(M_bar), which exist when |A/Inn| > 1. W506's combo 6
    # ([5,5,2,2,2,2]/[2,1]^4_[5,5]^2) undercount of 7 classes vs prebug
    # was traced to this. Keeping the flag so the path can be re-enabled
    # once a supplement-aware parametrization is implemented.
    USE_GENERAL_AUT_HOM := false;
fi;

if not IsBound(GENERAL_AUT_HOM_VERBOSE) then
    GENERAL_AUT_HOM_VERBOSE := false;
fi;

# Diagnostic: when true, after each successful GAH call, also run NSCR on the
# same (Q, M_bar) and record any class-count mismatch.  Skips NSCR when |Q|
# exceeds DIAG_GAH_MAX_Q_SIZE to keep the diagnostic tractable.  Divergent
# cases land in DIAG_GAH_DIFFERS (a list of records with Q/M_bar generators).
if not IsBound(DIAG_GAH_VS_NSCR) then
    DIAG_GAH_VS_NSCR := false;
fi;
if not IsBound(DIAG_GAH_MAX_Q_SIZE) then
    DIAG_GAH_MAX_Q_SIZE := 50000;
fi;
if not IsBound(DIAG_GAH_DIFFERS) then
    DIAG_GAH_DIFFERS := [];
fi;
# When set, each divergent (Q, M_bar) is appended immediately to this file
# (so we have data even if the run is interrupted).
if not IsBound(DIAG_GAH_DUMP_FILE) then
    DIAG_GAH_DUMP_FILE := fail;
fi;
# When set (string path), dump EVERY GAH/HBC call to this file (regardless of
# NSCR comparison) so we can later harvest large-Q cases for offline analysis.
if not IsBound(DIAG_GAH_DUMP_ALL_FILE) then
    DIAG_GAH_DUMP_ALL_FILE := fail;
fi;
# GAH writes its internal counts here at the end of each call (for debugging
# state-sensitivity bugs).
_GAH_LAST_INTERNALS := rec();

GeneralAutHomComplements := function(Q, M_bar, C)
    local idx, gensT, autT, isoPerm, autPerm, innGens, innT,
          qGens, qImages, phi, A, complsInA, gensC, result_raw,
          homClasses, Ai, ai_gens, ai_lifts, k, hom, base_imgs,
          c_a_map, ell, m_trial, a_lift, ok, c_idx, i, K_gens, K,
          _findRightOrderLift, result, byInv, key, bucket,
          candidate, is_dup, ai_gen, bucket_group, _dbg_t, _dbg,
          validTaus, stab_elts, orbitReps, canon, cand, stab_m,
          canon_seen;

    idx := Size(Q) / Size(M_bar);
    if idx = 1 then return [TrivialSubgroup(Q)]; fi;

    _dbg := GENERAL_AUT_HOM_VERBOSE;
    if _dbg then _dbg_t := Runtime(); fi;

    # Build phi: Q -> Aut(M_bar).
    gensT := SmallGeneratingSet(M_bar);
    autT := AutomorphismGroup(M_bar);
    isoPerm := IsomorphismPermGroup(autT);
    autPerm := Image(isoPerm);

    innGens := List(gensT, function(t)
        return Image(isoPerm, ConjugatorAutomorphismNC(M_bar, t));
    end);
    innT := Group(innGens);

    qGens := GeneratorsOfGroup(Q);
    qImages := List(qGens, function(g)
        local imgs;
        imgs := List(gensT, m -> m^g);
        return Image(isoPerm,
            GroupHomomorphismByImages(M_bar, M_bar, gensT, imgs));
    end);

    phi := GroupHomomorphismByImages(Q, autPerm, qGens, qImages);
    if phi = fail then return fail; fi;
    A := Image(phi);

    if _dbg then
        Print("            [GAH] built phi in ", Runtime()-_dbg_t,
              "ms, |A|=", Size(A), "\n");
        _dbg_t := Runtime();
    fi;

    complsInA := NonSolvableComplementClassReps(A, innT);
    if _dbg then
        Print("            [GAH] complsInA: ", Length(complsInA),
              " classes in ", Runtime()-_dbg_t, "ms\n");
        _dbg_t := Runtime();
    fi;
    if complsInA = [] then return fail; fi;

    gensC := GeneratorsOfGroup(C);
    result_raw := [];

    # Find a preimage of a_gen in Q with Order(lift) = Order(a_gen).
    # The default PreImagesRepresentative may return a higher-order lift
    # (differs by an element of C); multiplying by elements of C can fix
    # this. If no right-order lift exists cheaply, return fail.
    _findRightOrderLift := function(a_gen)
        local cand, target, c_elt, attempt;
        cand := PreImagesRepresentative(phi, a_gen);
        target := Order(a_gen);
        if Order(cand) = target then return cand; fi;
        # Iterate over C — bounded by Size(C); for non-S18 testing this is
        # small, for S18 W501 it's up to 2592, still fast.
        for c_elt in C do
            attempt := c_elt * cand;
            if Order(attempt) = target then return attempt; fi;
        od;
        return fail;
    end;

    # C trivial: each A_i gives one complement = phi^{-1}(A_i).
    if Length(gensC) = 0 then
        for Ai in complsInA do
            ai_gens := GeneratorsOfGroup(Ai);
            ai_lifts := List(ai_gens, _findRightOrderLift);
            if ForAny(ai_lifts, l -> l = fail) then return fail; fi;
            Add(result_raw, Group(ai_lifts));
        od;
        return result_raw;
    fi;

    homClasses := AllHomomorphismClasses(C, M_bar);
    if _dbg then
        Print("            [GAH] AllHomomorphismClasses: ",
              Length(homClasses), " classes in ",
              Runtime()-_dbg_t, "ms\n");
        _dbg_t := Runtime();
    fi;

    for Ai in complsInA do
        ai_gens := GeneratorsOfGroup(Ai);
        ai_lifts := List(ai_gens, _findRightOrderLift);
        if ForAny(ai_lifts, l -> l = fail) then return fail; fi;
        k := Length(ai_lifts);

        # Currently handle k = 0 and k = 1 with a^2 = 1. Return fail for
        # other cases so the caller can fall back to NSCR.
        if k > 1 then
            if _dbg then Print("            [GAH] k=", k, ", fail\n"); fi;
            return fail;
        fi;
        if k = 1 and Order(ai_gens[1]) <> 2 then
            if _dbg then
                Print("            [GAH] k=1 but Order(a)=",
                      Order(ai_gens[1]), " != 2, fail\n");
            fi;
            return fail;
        fi;
        if _dbg then
            Print("            [GAH] A_i with k=", k, ", lifts found in ",
                  Runtime()-_dbg_t, "ms\n");
            _dbg_t := Runtime();
        fi;

        for hom in homClasses do
            base_imgs := List(gensC, c -> Image(hom, c));

            if k = 0 then
                # Direct-product case: K = <phi_C(c) * c>_c.
                K := Group(List([1..Length(gensC)],
                                i -> base_imgs[i] * gensC[i]));
                if Size(K) = idx and Size(Intersection(K, M_bar)) = 1 then
                    Add(result_raw, K);
                fi;
            else
                # k = 1, a^2 = 1. Iterate tau = m in M_bar.
                # Collect all valid taus first, then dedup under Stab(hom)
                # action: tau ~ m_0^-1 * tau * (a_lift * m_0 * a_lift^-1)
                # for m_0 in Stab := C_{M_bar}(Image(hom)).
                a_lift := ai_lifts[1];
                c_a_map := List(gensC, c -> Image(hom, c^a_lift));
                validTaus := [];
                for m_trial in M_bar do
                    ell := m_trial * a_lift;
                    if ell^2 <> One(Q) then continue; fi;
                    ok := true;
                    for c_idx in [1..Length(gensC)] do
                        if ell * c_a_map[c_idx] * ell^-1
                           <> base_imgs[c_idx] then
                            ok := false; break;
                        fi;
                    od;
                    if ok then Add(validTaus, m_trial); fi;
                od;

                if Length(validTaus) = 0 then continue; fi;

                # Compute Stab = C_{M_bar}(Image(hom)).  Q-conjugation on K
                # within a fixed (A_i, hom) is generated by:
                #   - m_0 in Stab: tau -> m_0^-1 * tau * (a_lift * m_0 * a_lift^-1)
                #   - s(a) (the lift itself): tau -> a_lift^-1 * tau * a_lift
                # (The A_i-conjugation preserves hom when [hom] is A_i-fixed.)
                if Length(base_imgs) = 0 then
                    stab_elts := AsList(M_bar);
                elif ForAll(base_imgs, x -> x = One(M_bar)) then
                    stab_elts := AsList(M_bar);
                else
                    stab_elts := AsList(Centralizer(M_bar,
                                        Group(Filtered(base_imgs,
                                                       x -> x <> One(M_bar)))));
                fi;

                # Orbit dedup: for each tau, compute the minimum element
                # reachable under both actions to use as a dedup key.
                # CRITICAL: build K from the original m_trial (which is
                # known to satisfy equivariance), NOT from canon.  The
                # A_i orbit on m can map m_valid to a_gen(m_valid) which
                # does NOT satisfy equivariance whenever Image(hom)
                # generates a subgroup centralized only by Z(M_bar)=1.
                # Building K from such a "canon" gave Group(K_gens) with
                # Size = |M_bar|*idx (M_bar absorbed) — silently dropped
                # by the validity check, losing the orbit's K entirely.
                # Using m_trial preserves the K, and canon-tracking still
                # dedups orbit-equivalent K's.
                canon_seen := Set([]);
                for m_trial in validTaus do
                    canon := m_trial;
                    # Stab-action alone (tau -> m_0^-1 tau a(m_0))
                    for stab_m in stab_elts do
                        cand := stab_m^-1 * m_trial
                              * (a_lift * stab_m * a_lift^-1);
                        if cand < canon then canon := cand; fi;
                    od;
                    # A_i-action on tau (tau -> tau^{s(a)})
                    cand := a_lift^-1 * m_trial * a_lift;
                    if cand < canon then canon := cand; fi;
                    # Composed action: stab then A_i-shift
                    for stab_m in stab_elts do
                        cand := a_lift^-1 * (stab_m^-1 * m_trial
                              * (a_lift * stab_m * a_lift^-1)) * a_lift;
                        if cand < canon then canon := cand; fi;
                    od;
                    if canon in canon_seen then continue; fi;
                    AddSet(canon_seen, canon);
                    # Build K from m_trial (validated), not canon.
                    ell := m_trial * a_lift;
                    K_gens := Concatenation(
                        List([1..Length(gensC)],
                             i -> base_imgs[i] * gensC[i]),
                        [ell]);
                    K := Group(K_gens);
                    if Size(K) = idx
                       and Size(Intersection(K, M_bar)) = 1 then
                        Add(result_raw, K);
                    fi;
                od;
            fi;
        od;
    od;

    if _dbg then
        Print("            [GAH] raw candidates (post per-hom dedup): ",
              Length(result_raw), " in ", Runtime()-_dbg_t,
              "ms (inner loop)\n");
        _dbg_t := Runtime();
    fi;

    # Final dedup across (A_i, hom) pairs.  Per-hom stab-dedup catches
    # most duplicates within a fixed (A_i, hom), but two complements from
    # different (A_i, hom) pairs can still be Q-conjugate.  Use a cheap
    # multi-invariant (AbelianInvariants + orbit-size multiset on Q's
    # permutation domain) plus RepresentativeAction within buckets.
    # Orbit multiset is Q-conjugation invariant (conjugation permutes
    # points, so orbit sizes are preserved).
    result := [];
    byInv := rec();
    for candidate in result_raw do
        key := Concatenation(
            String(AbelianInvariants(candidate)),
            "|",
            String(SortedList(List(Orbits(candidate, MovedPoints(Q)),
                                   Length))));
        if not IsBound(byInv.(key)) then byInv.(key) := []; fi;
        bucket := byInv.(key);
        is_dup := false;
        for bucket_group in bucket do
            if RepresentativeAction(Q, candidate, bucket_group) <> fail then
                is_dup := true; break;
            fi;
        od;
        if not is_dup then
            Add(bucket, candidate);
            Add(result, candidate);
        fi;
    od;

    if _dbg then
        Print("            [GAH] dedup: ", Length(result),
              " classes in ", Runtime()-_dbg_t, "ms\n");
    fi;

    _GAH_LAST_INTERNALS := rec(
        Q_size := Size(Q),
        M_bar_size := Size(M_bar),
        C_size := Size(C),
        complsInA_count := Length(complsInA),
        homClasses_count := Length(homClasses),
        raw_count := Length(result_raw),
        dedup_count := Length(result),
        gensC_count := Length(gensC),
        gensC := gensC);

    return result;
end;

###############################################################################
# NormalSubgroupsBetween(S, M, N)
#
# Find all L with N <= L <= M where L is normal in S.
# The quotient M/N is an elementary abelian p-group (chief factor).
# We enumerate subspaces of M/N that are S-invariant.
###############################################################################

NormalSubgroupsBetween := function(S, M, N)
    local hom, MmodN, result, V, L,
          p, d, pcgs, mats, gen, mat, i, img, exps, module,
          submoduleBases, submodBasis, submodVecs, submodGens,
          vec, elm, subGrp;

    # If M = N, only M itself works
    if Size(M) = Size(N) then
        return [M];
    fi;

    # Map M -> M/N
    # Use SafeNaturalHomByNSG: catches internal GAP errors on large groups.
    hom := SafeNaturalHomByNSG(M, N);
    if hom = fail then
        return [M, N];  # Can't form quotient; return conservative approximation
    fi;
    MmodN := ImagesSource(hom);

    # M/N is elementary abelian (chief factor) for solvable chief factors
    # Non-solvable chief factors are non-abelian simple groups
    if not IsPGroup(MmodN) then
        p := fail;
    else
        p := PrimePGroup(MmodN);
    fi;
    if p = fail then
        # Non-abelian chief factor.
        # For simple M/N: the only S-normal subgroups between M and N are
        # M and N themselves (any normal subgroup of M/N is {1} or M/N).
        if IsSimpleGroup(MmodN) then
            return [M, N];
        fi;
        # For non-simple non-p-group (T^k with k>1):
        # The chief factor is a direct power T^k of a non-abelian simple group T.
        # S-normal subgroups between M and N must be normal in MmodN (since they
        # are between N and M) AND normalized by S.
        # Normal subgroups of T^k are exactly the sub-products T^I for subsets I,
        # giving 2^k candidates — much smaller than AllSubgroups.
        result := [M, N];
        for V in NormalSubgroups(MmodN) do
            if Size(V) > 1 and Size(V) < Size(MmodN) then
                L := PreImages(hom, V);
                if IsNormal(S, L) and not L in result then
                    Add(result, L);
                fi;
            fi;
        od;
        return result;
    fi;

    d := LogInt(Size(MmodN), p);

    # Dimension 0 or 1: only trivial and full submodules
    if d <= 1 then
        return [M, N];
    fi;

    # Compute the GF(p)-module structure of M/N under conjugation by S
    pcgs := Pcgs(MmodN);

    # Build action matrices: mat[i][j] = exponent of pcgs[j] in pcgs[i]^gen
    mats := [];
    for gen in GeneratorsOfGroup(S) do
        mat := [];
        for i in [1..d] do
            img := Image(hom, PreImagesRepresentative(hom, pcgs[i]) ^ gen);
            exps := ExponentsOfPcElement(pcgs, img);
            Add(mat, List(exps, x -> x * One(GF(p))));
        od;
        Add(mats, mat);
    od;

    # Handle trivial action (e.g., S centralizes M/N)
    if Length(mats) = 0 then
        mats := [IdentityMat(d, GF(p))];
    fi;

    # Create GModule and check irreducibility via MeatAxe
    module := GModuleByMats(mats, GF(p));

    if MTX.IsIrreducible(module) then
        # No proper S-invariant subspaces => only M and N
        return [M, N];
    fi;

    # Module is reducible: enumerate ALL S-invariant submodules of M/N.
    # Holt's lift step needs every S-invariant L/N between N and M, not just
    # one composition-series chain. MTX.BasesSubmodules returns one basis for
    # each invariant submodule, which we lift back to subgroups of M.
    result := [M, N];

    # BasesSubmodules includes the trivial and full submodules.
    submoduleBases := MTX.BasesSubmodules(module);

    # Each basis represents an S-invariant submodule; lift each back to a
    # normal subgroup between N and M.
    for submodBasis in submoduleBases do
        if Length(submodBasis) = 0 then
            # Trivial submodule = N (already in result)
            continue;
        fi;
        if Length(submodBasis) = d then
            # Full module = M (already in result)
            continue;
        fi;

        # Lift submodule basis vectors back to elements of MmodN
        submodVecs := List(submodBasis,
            row -> List(row, x -> IntFFE(x)));
        submodGens := [];
        for vec in submodVecs do
            elm := PcElementByExponents(pcgs, vec);
            Add(submodGens, elm);
        od;

        if Length(submodGens) > 0 then
            subGrp := Group(submodGens);
            L := PreImages(hom, subGrp);
            if Size(L) > Size(N) and Size(L) < Size(M) then
                Add(result, L);
            fi;
        fi;
    od;

    return result;
end;

###############################################################################
# RemoveConjugatesUnderP(P, subgroups)
#
# Remove P-conjugate duplicates from list of subgroups.
# Uses invariant bucketing to reduce comparisons.
###############################################################################

# InvariantKey(inv)
# Convert an invariant to a record key string, hashing if needed
# to stay within GAP's 1023-character record name limit.
InvariantKey := function(inv)
    local s;
    s := String(inv);
    if Length(s) > 900 then
        return _SimpleHashString(s);
    fi;
    return s;
end;

CheapSubgroupInvariant := function(H)
    local inv, abelianInv, moved;
    inv := [Size(H)];

    # Derived subgroup size (cheap, good discriminator)
    Add(inv, Size(DerivedSubgroup(H)));

    # Center size (cheap, good discriminator)
    Add(inv, Size(Center(H)));

    # Exponent (cheap, discriminating)
    Add(inv, Exponent(H));

    # Abelian invariants of abelianization (cheap, very discriminating)
    abelianInv := ShallowCopy(AbelianInvariants(H));
    Sort(abelianInv);
    Add(inv, abelianInv);

    # Orbit structure on moved points (conjugacy invariant for perm groups)
    moved := MovedPoints(H);
    if Length(moved) > 0 then
        Add(inv, SortedList(List(Orbits(H, moved), Length)));
    else
        Add(inv, []);
    fi;

    return inv;
end;

RemoveConjugatesUnderP := function(P, subgroups)
    local reps, byInv, bucketReps, H, inv, key, found, rep;

    if Length(subgroups) = 0 then
        return [];
    fi;

    # Bucket by cheap invariants (size + derived size + abelian invariants + orbits)
    byInv := rec();
    for H in subgroups do
        inv := CheapSubgroupInvariant(H);
        key := InvariantKey(inv);
        if not IsBound(byInv.(key)) then
            byInv.(key) := [];
        fi;
        Add(byInv.(key), H);
    od;

    # Deduplicate within each bucket (no cross-bucket comparisons needed)
    reps := [];
    for key in RecNames(byInv) do
        bucketReps := [];
        for H in byInv.(key) do
            found := false;
            for rep in bucketReps do
                if RepresentativeAction(P, H, rep) <> fail then
                    found := true;
                    break;
                fi;
            od;
            if not found then
                Add(bucketReps, H);
                Add(reps, H);
            fi;
        od;
    od;

    return reps;
end;

###############################################################################
# LiftThroughLayer(P, M, N, subgroups_containing_M, shifted_factors, offsets, partNormalizer)
#
# Core lifting step: Given subgroups containing M, find all FPF subdirect
# products containing N (but not necessarily M).
#
# For each S containing M:
#   - S itself is a candidate if it's FPF
#   - For each L with N <= L < M and L normal in S:
#     - Form S/L and find complements to M/L in S/L
#     - Lift complements back to S
#     - Check if they're FPF subdirect
###############################################################################

LiftThroughLayer := function(P, M, N, subgroups_containing_M, shifted_factors, offsets, partNormalizer)
    local lifted, S, L, hom, Q, M_bar, complements, C_bar, C, normalsBetween,
          fpfFilterForComplement, useEarlyFilter,
          outerNormGens, outerNormGensForL, N_S, N_M, outerNorm, gen,
          cachedOuterNormGens, cachedOuterNormComputed,
          t_normals, t_complements, t_dedup, t0, numBeforeDedup,
          cachedNormPM, outerNormBase,
          t_fpf_filter, t_outernorm, t0_fpf, t0_outernorm,
          numComplementsGenerated, numFPFAccepted, numH1Calls, numH1Fallbacks,
          numCoprimeSkips, layerSize, layerType, t_layer_start,
          hom_P, M_bar_P, numNonSplitSkips, m_gen, derivQ,
          complement_order, fpf_impossible, j, numFPFImpossibleSkips,
          _parentIdx, _numParents, _lastProgressTime;

    lifted := [];
    t_normals := 0;
    t_complements := 0;
    t_fpf_filter := 0;
    t_outernorm := 0;
    numComplementsGenerated := 0;
    numFPFAccepted := 0;
    numH1Calls := 0;
    numH1Fallbacks := 0;
    numCoprimeSkips := 0;
    numNonSplitSkips := 0;
    numFPFImpossibleSkips := 0;
    t_layer_start := Runtime();

    # Determine layer characteristics for profiling
    layerSize := Size(M) / Size(N);
    if IsPGroup(M) and IsPGroup(N) then
        layerType := Concatenation("abelian p=", String(PrimePGroup(M)), " dim=", String(LogInt(layerSize, PrimePGroup(M))));
    elif layerSize > 1 then
        layerType := Concatenation("size=", String(layerSize));
    else
        layerType := "trivial";
    fi;

    # Phase C1: Use partition normalizer (pre-stabilized by caller) for H^1 orbital.
    # The caller passes a group that normalizes all remaining chief series members,
    # ensuring orbit identification at this layer doesn't break subsequent layers.
    if partNormalizer <> fail and IsGroup(partNormalizer) then
        outerNormBase := partNormalizer;
    else
        outerNormBase := P;
    fi;

    # Cache Normalizer(outerNormBase, M) - M is fixed for the entire layer
    # Used for outer normalizer computation in H^1 orbital method
    cachedNormPM := Normalizer(outerNormBase, M);

    # OPTIMIZATION: Precompute P -> P/N quotient homomorphism once per layer.
    # For the common case L = N, we reuse this instead of computing
    # NaturalHomomorphismByNormalSubgroup(S, N) for each parent S separately.
    # Image(hom_P, S) gives S/N as subgroup of P/N, much cheaper than
    # building a new quotient group for each S (~1ms vs ~12ms).
    # GUARD: Only use when [P:N] is small. Large [P:N] causes complement
    # computation to work in a bloated representation (degree [P:N] instead
    # of [S:N]), which can be catastrophically slower for downstream H^1/
    # ComplementClassesRepresentatives calls.
    if Size(N) > 1 and Size(P) / Size(N) <= 200 then
        hom_P := SafeNaturalHomByNSG(P, N);
        if hom_P <> fail then
            M_bar_P := Image(hom_P, M);
        else
            M_bar_P := fail;
        fi;
    else
        hom_P := fail;
        M_bar_P := fail;
    fi;

    _parentIdx := 0;
    _numParents := Length(subgroups_containing_M);
    _lastProgressTime := Runtime();

    for S in subgroups_containing_M do
        _parentIdx := _parentIdx + 1;

        # Progress logging: for non-elementary-abelian layers (expensive per-parent),
        # log every parent. For elementary abelian layers, log every 60s or 500 parents.
        if layerSize > 4 and not (IsPGroup(M) and IsPGroup(N)) then
            # Non-elementary-abelian chief factor (e.g., A_n) - log every parent
            if _parentIdx = 1 or Runtime() - _lastProgressTime > 30000 or
               _parentIdx mod 10 = 0 then
                Print("      [layer ", layerType, "] parent ", _parentIdx, "/", _numParents,
                      " |S|=", Size(S),
                      " (", numFPFAccepted, " FPF, ", numComplementsGenerated, " compls, ",
                      Int((Runtime() - t_layer_start)/1000), "s elapsed)\n");
                _lastProgressTime := Runtime();
                if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
                    PrintTo(_HEARTBEAT_FILE, "alive ",
                            Int(Runtime() / 1000), "s ",
                            _CURRENT_COMBO, " layer [", layerType,
                            "] parent ", _parentIdx, "/", _numParents, "\n");
                fi;
            fi;
        elif _numParents > 50 and (Runtime() - _lastProgressTime > 60000 or
           (_parentIdx mod 500 = 0)) then
            Print("      [layer ", layerType, "] parent ", _parentIdx, "/", _numParents,
                  " (", numFPFAccepted, " FPF, ", numComplementsGenerated, " compls, ",
                  Int((Runtime() - t_layer_start)/1000), "s elapsed)\n");
            _lastProgressTime := Runtime();
            # Update heartbeat if available
            if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
                PrintTo(_HEARTBEAT_FILE, "alive ",
                        Int(Runtime() / 1000), "s ",
                        _CURRENT_COMBO, " layer [", layerType,
                        "] parent ", _parentIdx, "/", _numParents, "\n");
            fi;
        fi;

        # S itself is a candidate (already contains M >= N)
        if IsFPFSubdirect(S, shifted_factors, offsets) then
            Add(lifted, S);
        fi;

        # Find all L with N <= L <= M and L normal in S
        t0 := Runtime();
        normalsBetween := NormalSubgroupsBetween(S, M, N);
        t_normals := t_normals + (Runtime() - t0);

        # Cache outer normalizer computation per S (shared across L values)
        cachedOuterNormComputed := false;
        cachedOuterNormGens := [];

        for L in normalsBetween do
            # Skip L = M (that's S itself, already handled)
            if Size(L) = Size(M) then
                continue;
            fi;

            # Form quotient S/L
            # OPTIMIZATION: When L = N and many parents, reuse precomputed P -> P/N
            # homomorphism. Image(hom_P, S) gives S/N as subgroup of P/N, avoiding
            # expensive per-parent NaturalHomomorphismByNormalSubgroup construction.
            # Only use for large parent counts (>10), since the quotient may have a
            # larger degree representation than a fresh per-parent quotient.
            if Size(L) = Size(N) and hom_P <> fail and Length(subgroups_containing_M) > 10 then
                hom := hom_P;
                Q := Image(hom_P, S);
                M_bar := M_bar_P;
            else
                hom := SafeNaturalHomByNSG(S, L);
                if hom = fail then
                    continue;  # Skip this L for this parent S
                fi;
                Q := ImagesSource(hom);
                M_bar := Image(hom, M);
            fi;

            # FPF IMPOSSIBILITY TEST: Any complement C to M/L in S/L has
            # |C_lifted| = (|S|/|M|) * |L|. For C_lifted to be transitive
            # on each orbit of degree d_i, we need d_i | |C_lifted|.
            # This cheap arithmetic check catches cases where NO complement
            # can ever be FPF (e.g., 2-group complement on orbit of odd prime degree).
            complement_order := (Size(S) / Size(M)) * Size(L);
            fpf_impossible := false;
            for j in [1..Length(shifted_factors)] do
                if complement_order mod NrMovedPoints(shifted_factors[j]) <> 0 then
                    fpf_impossible := true;
                    break;
                fi;
            od;
            if USE_FPF_IMPOSSIBILITY and fpf_impossible then
                numFPFImpossibleSkips := numFPFImpossibleSkips + 1;
                continue;
            fi;

            # OPTIMIZATION: Create FPF filter for early pruning
            # This filter checks if the lifted complement is FPF before collecting it
            fpfFilterForComplement := function(C_bar)
                local C_lifted;
                C_lifted := PreImages(hom, C_bar);
                return IsFPFSubdirect(C_lifted, shifted_factors, offsets);
            end;

            # Decide whether to use early filtering
            # Use early filtering when:
            # 1. We're using H^1 method (can integrate filter)
            # 2. Expected complement count is large enough to benefit
            useEarlyFilter := USE_H1_COMPLEMENTS and
                              IsElementaryAbelian(M_bar) and
                              Size(M_bar) > 1 and
                              Size(Q) / Size(M_bar) > 10;

            # Find complements to M/L in S/L
            # These are subgroups C_bar of Q with C_bar * M_bar = Q and C_bar ∩ M_bar = 1
            t0 := Runtime();
            complements := [];

            # FAST NON-SPLIT TEST for dim-1 central extensions:
            # For a CENTRAL extension 1 -> C_p -> Q -> G -> 1 (C_p <= Z(Q)),
            # the extension splits iff the generator of C_p is NOT in [Q,Q].
            # This is because complements correspond to sections Q -> Q/C_p,
            # which factor through Q^ab = Q/[Q,Q].
            # IMPORTANT: Only applies when M_bar is CENTRAL in Q. For non-central
            # extensions, complement existence is governed by H^1(G, M) with
            # non-trivial action, where m_gen in [Q,Q] does NOT imply non-split.
            # Cost: centrality check + DerivedSubgroup(Q) (~0.1ms per parent).
            # Benefit: Skips H^1/ComplementClassesRepresentatives (~12ms per parent).
            if USE_NONSPLIT_TEST and IsPrimeInt(Size(M_bar)) then
                m_gen := First(GeneratorsOfGroup(M_bar), g -> Order(g) > 1);
                if m_gen <> fail and ForAll(GeneratorsOfGroup(Q), q -> q*m_gen = m_gen*q) then
                    derivQ := DerivedSubgroup(Q);
                    if m_gen in derivQ then
                        numNonSplitSkips := numNonSplitSkips + 1;
                        t_complements := t_complements + (Runtime() - t0);
                        continue;
                    fi;
                fi;
            fi;

            # Phase 2 Optimization: Early coprime termination (Schur-Zassenhaus)
            # If gcd(|Q/M_bar|, |M_bar|) = 1, there's exactly one complement class.
            # Use HallSubgroup (fast Sylow-based) instead of ComplementClassesRepresentatives.
            if Gcd(Size(Q) / Size(M_bar), Size(M_bar)) = 1 then
                H1_TIMING_STATS.coprime_skips := H1_TIMING_STATS.coprime_skips + 1;
                numCoprimeSkips := numCoprimeSkips + 1;
                # M_bar is the unique Sylow p-subgroup (normal, coprime index).
                # The Hall p'-subgroup is the unique complement (Schur-Zassenhaus).
                complements := CallFuncList(function()
                    local p, pi_comp, H, result;
                    p := SmallestPrimeDivisor(Size(M_bar));
                    pi_comp := Filtered(Set(Factors(Size(Q))), q -> q <> p);
                    if Length(pi_comp) = 0 then
                        return [];  # Q = M_bar, no complement needed
                    fi;
                    if IsSolvableGroup(Q) then
                        H := HallSubgroup(Q, pi_comp);
                        if H <> fail then
                            return [H];
                        fi;
                    fi;
                    # Fallback for non-solvable or HallSubgroup failure
                    result := fail;
                    BreakOnError := false;
                    result := CALL_WITH_CATCH(ComplementClassesRepresentatives, [Q, M_bar]);
                    BreakOnError := true;
                    if result[1] = true then
                        return result[2];
                    fi;
                    return [];
                end, []);
                # Apply FPF filter to the complement(s)
                if IsList(complements) and Length(complements) > 0 then
                    complements := Filtered(complements, fpfFilterForComplement);
                else
                    complements := [];
                fi;
            # Try H^1-based method for elementary abelian M_bar
            elif USE_H1_COMPLEMENTS and IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
                _TryLoadCohomology();
                if _COHOMOLOGY_LOADED then
                    # PHASE 2 OPTIMIZATION: Use H^1 orbital method when:
                    # 1. H^1 dimension is expected to be large (many complements)
                    # 2. We have OUTER normalizers that give non-trivial action on H^1
                    #
                    # Key insight: Elements of S act by INNER automorphisms on H^1,
                    # which are trivial. To get non-trivial orbits, we need elements
                    # of N_P(S) ∩ N_P(M) that are OUTSIDE S.

                    _TryLoadH1Orbital();

                    if _H1_ORBITAL_LOADED and IsBound(USE_H1_ORBITAL) and USE_H1_ORBITAL
                       and Length(subgroups_containing_M) <= 100000 then
                        # Compute outer normalizer: N_P(S) ∩ N_P(M) elements outside S
                        # These provide the non-trivial outer automorphism action on H^1.
                        # Cache this computation per S (reused across L values)
                        if not cachedOuterNormComputed then
                            t0_outernorm := Runtime();
                            cachedOuterNormGens := [];

                            # Compute N_outerNormBase(S) ∩ N_outerNormBase(M)
                            # Using outerNormBase (partition normalizer if available)
                            # gives more outer normalizer elements for H^1 orbit reduction
                            # N_M is cached at layer level (M is fixed across all S)
                            N_S := Normalizer(outerNormBase, S);
                            outerNorm := Intersection(N_S, cachedNormPM);

                            # Extract generators that are outside S AND don't centralize S
                            # Elements that centralize S act trivially on Q = S/L, hence trivially on H^1
                            for gen in GeneratorsOfGroup(outerNorm) do
                                if not gen in S then
                                    if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                                        Add(cachedOuterNormGens, gen);
                                    fi;
                                fi;
                            od;
                            cachedOuterNormComputed := true;
                            t_outernorm := t_outernorm + (Runtime() - t0_outernorm);
                        fi;

                        # Filter outer normalizer generators to those normalizing L.
                        # This is required for the action on Q = S/L to be well-defined:
                        # if n doesn't normalize L, then the map q -> n^{-1}qn doesn't
                        # descend to a well-defined action on S/L.
                        if Size(L) > 1 then
                            outerNormGens := Filtered(cachedOuterNormGens,
                                gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));
                        else
                            outerNormGens := cachedOuterNormGens;
                        fi;

                        # OPT 5: Orbital method applies FPF filter via 8th argument
                        # But the processing loop should still do its own FPF check
                        # because the filter operates on the quotient complement C_bar,
                        # and lifting back through L may change FPF properties
                        useEarlyFilter := false;

                        if Length(outerNormGens) > 0 then
                            # Use orbital method with outer normalizer action
                            # OPT 5: Pass FPF filter to orbital method for early rejection
                            complements := CallFuncList(function()
                                local h1_start, h1_result;
                                h1_start := Runtime();
                                # Pass outer normalizer info + FPF filter (8th arg)
                                h1_result := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, hom, P, fpfFilterForComplement);
                                H1_TIMING_STATS.h1_time := H1_TIMING_STATS.h1_time + (Runtime() - h1_start);
                                H1_TIMING_STATS.h1_calls := H1_TIMING_STATS.h1_calls + 1;
                                return h1_result;
                            end, []);
                        else
                            # No outer normalizers - orbital method won't help
                            # Fall back to standard H^1 enumeration with FPF filter
                            complements := CallFuncList(function()
                                local h1_start, h1_result;
                                h1_start := Runtime();
                                h1_result := GetComplementsViaH1(Q, M_bar, fpfFilterForComplement);
                                H1_TIMING_STATS.h1_time := H1_TIMING_STATS.h1_time + (Runtime() - h1_start);
                                H1_TIMING_STATS.h1_calls := H1_TIMING_STATS.h1_calls + 1;
                                return h1_result;
                            end, []);
                            useEarlyFilter := true;  # Complements already FPF-filtered
                        fi;
                    else
                        # Fall back to standard H^1 method with FPF filter
                        complements := CallFuncList(function()
                            local h1_start, h1_result;
                            h1_start := Runtime();
                            h1_result := GetComplementsViaH1(Q, M_bar, fpfFilterForComplement);
                            H1_TIMING_STATS.h1_time := H1_TIMING_STATS.h1_time + (Runtime() - h1_start);
                            H1_TIMING_STATS.h1_calls := H1_TIMING_STATS.h1_calls + 1;
                            return h1_result;
                        end, []);
                        useEarlyFilter := true;  # Complements already FPF-filtered
                    fi;
                fi;
            fi;

            # Handle fail return from H^1 methods - must fall back to GAP
            if complements = fail then
                complements := [];
                numH1Fallbacks := numH1Fallbacks + 1;
                # H^1 method FAILED (not "no complements") - force fallback
                if IsSolvableGroup(M_bar) or IsSolvableGroup(Q) then
                    complements := ComplementClassesRepresentatives(Q, M_bar);
                    H1_TIMING_STATS.fallback_calls := H1_TIMING_STATS.fallback_calls + 1;
                else
                    complements := NonSolvableComplementClassReps(Q, M_bar);
                    H1_TIMING_STATS.fallback_calls := H1_TIMING_STATS.fallback_calls + 1;
                fi;
            fi;

            # Fallback to standard methods if H^1 wasn't used
            if Length(complements) = 0 and not (USE_H1_COMPLEMENTS and IsElementaryAbelian(M_bar) and Size(M_bar) > 1) then
                if IsSolvableGroup(M_bar) or IsSolvableGroup(Q) then
                    complements := ComplementClassesRepresentatives(Q, M_bar);
                    H1_TIMING_STATS.fallback_calls := H1_TIMING_STATS.fallback_calls + 1;
                else
                    # Non-solvable M_bar (e.g., A_n chief factors).
                    # Fast path for small index [Q:M_bar]:
                    # Find complements by searching for subgroups of the right
                    # order with trivial intersection with M_bar.
                    if layerSize > 60 then
                        Print("        nonsol p", _parentIdx, "/", _numParents,
                              " |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
                              " idx=", Size(Q)/Size(M_bar), "\n");
                    fi;
                    complements := CallFuncList(function()
                        local idx, compReps, g, C, c, transversal, t, gens,
                              subC, result, _t0, _autResult, _ghResult,
                              _t1, _diagNscr, _tfResult;
                        idx := Size(Q) / Size(M_bar);

                        # For index 2 (most common: S_n/A_n):
                        # A complement is generated by any involution in Q\M_bar.
                        # All such complements are conjugate under M_bar.
                        if idx = 2 then
                            # Find any element outside M_bar
                            for g in GeneratorsOfGroup(Q) do
                                if not g in M_bar then
                                    if g^2 = One(Q) then
                                        return [Group([g])];
                                    fi;
                                fi;
                            od;
                            # Generators didn't give us an involution directly.
                            # Try products and powers of generators.
                            for g in GeneratorsOfGroup(Q) do
                                if not g in M_bar then
                                    t := g^2;  # t in M_bar
                                    if t = One(Q) then
                                        return [Group([g])];
                                    fi;
                                    subC := List([1..50], i -> PseudoRandom(M_bar));
                                    for c in subC do
                                        if (g * c)^2 = One(Q) then
                                            return [Group([g * c])];
                                        fi;
                                    od;
                                fi;
                            od;
                            # Extension might not split - no complement exists
                            return [];
                        fi;

                        # TF-DATABASE LOOKUP (Holt): if Q's subgroup lattice is
                        # cached (or within size bound), derive complements by
                        # filtering subgroups for |H|=idx and H cap M_bar = 1.
                        # Isomorphic Q across parents all reuse one cache entry,
                        # giving the 10-100x speedup Holt reports.
                        # On fail, fall through to existing helpers below.
                        if USE_TF_DATABASE then
                            _t0 := Runtime();
                            _tfResult := EnumerateComplementsViaTFDatabase(Q, M_bar);
                            if _tfResult <> fail then
                                if layerSize > 60 then
                                    Print("          TFDB: ", Length(_tfResult),
                                          " complements (", Runtime()-_t0, "ms, ",
                                          "hits=", TF_LOOKUP_STATS.hits,
                                          "/calls=", TF_LOOKUP_STATS.calls, ")\n");
                                fi;
                                return _tfResult;
                            fi;
                            if layerSize > 60 then
                                Print("          TFDB: miss/oversized (",
                                      Runtime()-_t0, "ms, |Q|=", Size(Q), ")\n");
                            fi;
                        fi;

                        # For index > 2 with non-abelian simple M_bar:
                        # Since Z(M_bar) = 1, H^2(Q/M_bar, Z(M_bar)) = 0,
                        # so the extension ALWAYS splits. Find a complement.

                        # CENTRALIZER FAST PATH: For non-abelian simple M_bar,
                        # Z(M_bar) = 1 implies Centralizer(Q, M_bar) ∩ M_bar = 1.
                        # If |Centralizer(Q, M_bar)| = [Q:M_bar], the centralizer
                        # is ONE complement (M_bar is a direct factor of Q).
                        # It is the UNIQUE complement only when C is not isomorphic
                        # to M_bar. When C ≅ M_bar (e.g., Q = A_5 × A_5), there
                        # are additional "diagonal" complements {(φ(c),c) : c ∈ C}
                        # for φ ∈ Aut(M_bar), giving |Out(M_bar)| extra classes.
                        _t0 := Runtime();
                        C := Centralizer(Q, M_bar);
                        if layerSize > 60 then
                            Print("          centralizer: |C|=", Size(C),
                                  " (", Runtime()-_t0, "ms)\n");
                        fi;
                        if Size(C) = idx and Size(Intersection(C, M_bar)) = 1 then
                            # C is ONE complement. It is the UNIQUE conjugacy
                            # class of complement iff Hom(C, M_bar) is trivial.
                            # Since C centralizes M_bar, its action on M_bar is
                            # trivial, so 1-cocycles reduce to Hom(C, M_bar),
                            # and complements correspond to Hom(C, M_bar) modulo
                            # Inner(M_bar)-conjugation.
                            #
                            # For non-abelian simple M_bar, Hom(C, M_bar) is
                            # trivial iff every homomorphic image of C in M_bar
                            # is trivial. Any non-trivial image has order > 1
                            # dividing both |C| and |M_bar|. Hence:
                            #   gcd(|C|, |M_bar|) = 1  =>  Hom(C, M_bar) = {1}.
                            # (And conversely, if gcd > 1 with prime p, then C
                            # has a C_p quotient (Sylow-p abelianization) and
                            # M_bar has a cyclic subgroup of order p, yielding
                            # a non-trivial hom C -> C_p <= M_bar.)
                            #
                            # PREVIOUS CHECK WAS WRONG: it looked for a
                            # composition factor of C with size = |M_bar|,
                            # but missed every case where C has a smaller
                            # composition factor whose order divides |M_bar|
                            # (nearly all real cases — e.g., |C|=64 vs
                            # |M_bar|=168 has gcd=8, so non-trivial homs
                            # C -> C_2 <= M_bar exist, but the old check saw
                            # no size-168 factor in C and wrongly declared
                            # uniqueness, returning only [C] and missing
                            # the other complement conjugacy classes).
                            if Gcd(Size(C), Size(M_bar)) = 1 then
                                if layerSize > 60 then
                                    Print("          -> unique centralizer complement (coprime orders)\n");
                                fi;
                                return [C];
                            fi;
                            # gcd > 1: additional complements from Hom(C, M_bar).
                            # Direct-product structure lets us enumerate them
                            # explicitly via AllHomomorphismClasses — far
                            # cheaper than NSCR's maximal-subgroup descent.
                            if USE_HOM_CENTRALIZER_PATH then
                                if layerSize > 60 then
                                    Print("          -> Hom-based centralizer enumeration (gcd(",
                                          Size(C), ",", Size(M_bar), ")=",
                                          Gcd(Size(C), Size(M_bar)), ")\n");
                                    _t0 := Runtime();
                                fi;
                                result := HomBasedCentralizerComplements(C, M_bar);
                                if layerSize > 60 then
                                    Print("          -> Hom-based: ", Length(result),
                                          " complements (", Runtime()-_t0, "ms)\n");
                                fi;
                                if DIAG_GAH_DUMP_ALL_FILE <> fail then
                                    AppendTo(DIAG_GAH_DUMP_ALL_FILE,
                                        "Add(GAH_ALL_CALLS, rec(",
                                        "source := \"HBC\", ",
                                        "Q_size := ", Size(Q), ", ",
                                        "M_bar_size := ", Size(M_bar), ", ",
                                        "C_size := ", Size(C), ", ",
                                        "idx := ", Size(Q) / Size(M_bar), ", ",
                                        "gah_count := ", Length(result), ", ",
                                        "Q_gens := ", GeneratorsOfGroup(Q), ", ",
                                        "M_bar_gens := ", GeneratorsOfGroup(M_bar),
                                        "));\n");
                                fi;
                                if DIAG_GAH_VS_NSCR
                                   and Size(Q) <= DIAG_GAH_MAX_Q_SIZE then
                                    _t1 := Runtime();
                                    _diagNscr := NonSolvableComplementClassReps(Q, M_bar);
                                    if Length(_diagNscr) <> Length(result) then
                                        Add(DIAG_GAH_DIFFERS, rec(
                                            source := "HBC",
                                            Q_size := Size(Q),
                                            M_bar_size := Size(M_bar),
                                            C_size := Size(C),
                                            idx := Size(Q) / Size(M_bar),
                                            gah_count := Length(result),
                                            nscr_count := Length(_diagNscr),
                                            Q_gens := GeneratorsOfGroup(Q),
                                            M_bar_gens := GeneratorsOfGroup(M_bar),
                                            gah_reps := result,
                                            nscr_reps := _diagNscr));
                                        Print("          ! HBC-vs-NSCR mismatch: HBC=",
                                              Length(result), " NSCR=",
                                              Length(_diagNscr),
                                              " |Q|=", Size(Q),
                                              " |M_bar|=", Size(M_bar),
                                              " |C|=", Size(C),
                                              " (NSCR ", Runtime()-_t1, "ms)\n");
                                        if DIAG_GAH_DUMP_FILE <> fail then
                                            AppendTo(DIAG_GAH_DUMP_FILE,
                                                "Add(DIAG_GAH_DIFFERS_LOADED, rec(",
                                                "source := \"HBC\", ",
                                                "Q_size := ", Size(Q), ", ",
                                                "M_bar_size := ", Size(M_bar), ", ",
                                                "C_size := ", Size(C), ", ",
                                                "idx := ", Size(Q) / Size(M_bar), ", ",
                                                "gah_count := ", Length(result), ", ",
                                                "nscr_count := ", Length(_diagNscr), ", ",
                                                "Q_gens := ", GeneratorsOfGroup(Q), ", ",
                                                "M_bar_gens := ", GeneratorsOfGroup(M_bar),
                                                "));\n");
                                        fi;
                                    fi;
                                fi;
                                return result;
                            fi;
                            if layerSize > 60 then
                                Print("          -> centralizer + extra homs (gcd(",
                                      Size(C), ",", Size(M_bar), ")=",
                                      Gcd(Size(C), Size(M_bar)), ") — fall through\n");
                            fi;
                        fi;

                        # GENERAL AUT-HOM path: combines AutReduction with
                        # Hom twists and tau cocycle corrections. Handles
                        # the non-direct-product case |C| < idx with
                        # gcd(|C|, |M_bar|) > 1 that AutReduction alone
                        # cannot (and that NSCR used to chug through).
                        # Returns fail when |gens(A_i)| > 1 with A_i
                        # non-involution — caller falls through to NSCR.
                        if USE_GENERAL_AUT_HOM then
                            _t0 := Runtime();
                            _ghResult := GeneralAutHomComplements(Q, M_bar, C);
                            if _ghResult <> fail then
                                if layerSize > 60 then
                                    Print("          GeneralAutHom: ", Length(_ghResult),
                                          " complements (", Runtime()-_t0, "ms)\n");
                                fi;
                                if DIAG_GAH_DUMP_ALL_FILE <> fail then
                                    AppendTo(DIAG_GAH_DUMP_ALL_FILE,
                                        "Add(GAH_ALL_CALLS, rec(",
                                        "source := \"GAH\", ",
                                        "Q_size := ", Size(Q), ", ",
                                        "M_bar_size := ", Size(M_bar), ", ",
                                        "C_size := ", Size(C), ", ",
                                        "idx := ", Size(Q) / Size(M_bar), ", ",
                                        "gah_count := ", Length(_ghResult), ", ",
                                        "Q_gens := ", GeneratorsOfGroup(Q), ", ",
                                        "M_bar_gens := ", GeneratorsOfGroup(M_bar),
                                        "));\n");
                                fi;
                                if DIAG_GAH_VS_NSCR
                                   and Size(Q) <= DIAG_GAH_MAX_Q_SIZE then
                                    _t1 := Runtime();
                                    _diagNscr := NonSolvableComplementClassReps(Q, M_bar);
                                    if Length(_diagNscr) <> Length(_ghResult) then
                                        Add(DIAG_GAH_DIFFERS, rec(
                                            source := "GAH",
                                            Q_size := Size(Q),
                                            M_bar_size := Size(M_bar),
                                            C_size := Size(C),
                                            idx := Size(Q) / Size(M_bar),
                                            gah_count := Length(_ghResult),
                                            nscr_count := Length(_diagNscr),
                                            Q_gens := GeneratorsOfGroup(Q),
                                            M_bar_gens := GeneratorsOfGroup(M_bar),
                                            gah_reps := _ghResult,
                                            nscr_reps := _diagNscr,
                                            internals := _GAH_LAST_INTERNALS,
                                            C_gens_at_diff := GeneratorsOfGroup(C)));
                                        Print("          ! GAH-vs-NSCR mismatch: GAH=",
                                              Length(_ghResult), " NSCR=",
                                              Length(_diagNscr),
                                              " |Q|=", Size(Q),
                                              " |M_bar|=", Size(M_bar),
                                              " |C|=", Size(C),
                                              " (NSCR ", Runtime()-_t1, "ms)\n");
                                        if DIAG_GAH_DUMP_FILE <> fail then
                                            AppendTo(DIAG_GAH_DUMP_FILE,
                                                "Add(DIAG_GAH_DIFFERS_LOADED, rec(",
                                                "source := \"GAH\", ",
                                                "Q_size := ", Size(Q), ", ",
                                                "M_bar_size := ", Size(M_bar), ", ",
                                                "C_size := ", Size(C), ", ",
                                                "idx := ", Size(Q) / Size(M_bar), ", ",
                                                "gah_count := ", Length(_ghResult), ", ",
                                                "nscr_count := ", Length(_diagNscr), ", ",
                                                "homClasses := ",
                                                  _GAH_LAST_INTERNALS.homClasses_count, ", ",
                                                "raw_count := ",
                                                  _GAH_LAST_INTERNALS.raw_count, ", ",
                                                "dedup_count := ",
                                                  _GAH_LAST_INTERNALS.dedup_count, ", ",
                                                "C_gens := ",
                                                  GeneratorsOfGroup(C), ", ",
                                                "Q_gens := ", GeneratorsOfGroup(Q), ", ",
                                                "M_bar_gens := ", GeneratorsOfGroup(M_bar),
                                                "));\n");
                                        fi;
                                    fi;
                                fi;
                                return _ghResult;
                            fi;
                            if layerSize > 60 then
                                Print("          GeneralAutHom: not applicable (",
                                      Runtime()-_t0, "ms)\n");
                            fi;
                        fi;

                        # Centralizer is not the unique complement.
                        # Try Aut(M_bar) reduction before expensive fallbacks.
                        _t0 := Runtime();
                        _autResult := NonAbelianComplementsViaAut(Q, M_bar, C);
                        if _autResult <> fail then
                            if layerSize > 60 then
                                Print("          AutReduction: ", Length(_autResult),
                                      " complements (", Runtime()-_t0, "ms)\n");
                            fi;
                            return _autResult;
                        fi;
                        if layerSize > 60 then
                            Print("          AutReduction: not applicable (", Runtime()-_t0, "ms)\n");
                        fi;

                        # Try GAP's built-in (with catch for errors/hangs)
                        if idx <= 120 then
                            if layerSize > 60 then
                                Print("          trying CCR (idx=", idx, ")...\n");
                            fi;
                            _t0 := Runtime();
                            BreakOnError := false;
                            result := CALL_WITH_CATCH(ComplementClassesRepresentatives, [Q, M_bar]);
                            BreakOnError := true;
                            if result[1] = true and IsList(result[2]) then
                                if layerSize > 60 then
                                    Print("          CCR: ", Length(result[2]),
                                          " complements (", Runtime()-_t0, "ms)\n");
                                fi;
                                return result[2];
                            fi;
                            if layerSize > 60 then
                                Print("          CCR failed (", Runtime()-_t0, "ms)\n");
                            fi;
                        fi;

                        # Fallback: maximal subgroup descent
                        if layerSize > 60 then
                            Print("          trying NonSolvableComplementClassReps...\n");
                            _t0 := Runtime();
                        fi;
                        result := NonSolvableComplementClassReps(Q, M_bar);
                        if layerSize > 60 then
                            Print("          NSCR: ", Length(result),
                                  " complements (", Runtime()-_t0, "ms)\n");
                        fi;
                        return result;
                    end, []);
                    H1_TIMING_STATS.fallback_calls := H1_TIMING_STATS.fallback_calls + 1;
                fi;
            fi;

            t_complements := t_complements + (Runtime() - t0);

            numComplementsGenerated := numComplementsGenerated + Length(complements);

            # Process complements (some may already be FPF-filtered)
            t0_fpf := Runtime();
            for C_bar in complements do
                # Lift back to S
                C := PreImages(hom, C_bar);

                # Check FPF subdirect condition (skip if early filtering was used)
                if useEarlyFilter then
                    # Already filtered, just add
                    Add(lifted, C);
                    numFPFAccepted := numFPFAccepted + 1;
                elif IsFPFSubdirect(C, shifted_factors, offsets) then
                    Add(lifted, C);
                    numFPFAccepted := numFPFAccepted + 1;
                fi;
            od;
            t_fpf_filter := t_fpf_filter + (Runtime() - t0_fpf);
        od;
    od;

    # No intermediate dedup needed within LiftThroughLayer.
    # Proof: Inputs (subgroups_containing_M) are pairwise non-P-conjugate (invariant).
    # For non-conjugate parents S1 ≇_P S2, complements C1 from S1 and C2 from S2
    # satisfy C1·M = S1 ≇_P S2 = C2·M, so C1 ≇_P C2.
    # H^1 returns class reps within each (S,L), ensuring no intra-parent duplicates.
    t_dedup := 0;
    numBeforeDedup := Length(lifted);

    if t_normals + t_complements > 500 or (Runtime() - t_layer_start) > 1000 then
        Print("    LiftThroughLayer [", layerType, "] ",
              (Runtime() - t_layer_start), "ms: normals=", t_normals,
              "ms compl=", t_complements, "ms fpf_filt=", t_fpf_filter,
              "ms outernorm=", t_outernorm, "ms\n");
        Print("      ", Length(subgroups_containing_M), " parents, ",
              numComplementsGenerated, " complements generated, ",
              numFPFAccepted, " FPF accepted (", numBeforeDedup, " total lifted)\n");
        if numCoprimeSkips > 0 then
            Print("      coprime_skips=", numCoprimeSkips, "\n");
        fi;
        if numNonSplitSkips > 0 then
            Print("      nonsplit_skips=", numNonSplitSkips, "\n");
        fi;
        if numFPFImpossibleSkips > 0 then
            Print("      fpf_impossible_skips=", numFPFImpossibleSkips, "\n");
        fi;
        if numH1Fallbacks > 0 then
            Print("      H^1 fallbacks=", numH1Fallbacks, "\n");
        fi;
    fi;

    return lifted;
end;

###############################################################################
# LayerNeedsRefinement(layerSize)
#
# Check if a chief series layer is too large and needs refinement.
# Thresholds based on Holt 2010: 2^8 has 417,199 subgroups.
###############################################################################

LayerNeedsRefinement := function(layerSize)
    # Thresholds where subgroup enumeration becomes impractical
    if layerSize >= 64 then      # 2^6
        return true;
    fi;
    if layerSize >= 243 then     # 3^5
        return true;
    fi;
    if layerSize >= 625 then     # 5^4
        return true;
    fi;
    if layerSize >= 2401 then    # 7^4
        return true;
    fi;
    return false;
end;

###############################################################################
# RefineChiefSeriesLayer(G, M, N)
#
# Find G-invariant intermediate subgroups between M and N to split a large
# elementary abelian layer into smaller steps.
#
# IMPROVED: Uses MeatAxe-style module decomposition when available.
# For M/N as a GF(p)-module under G-conjugation, finds composition factors.
#
# Returns: List [M, L1, L2, ..., N] of intermediate normal subgroups
###############################################################################

RefineChiefSeriesLayer := function(G, M, N)
    local layerSize, hom, MmodN, p, dim, targetDim, V, pcgs, refinement,
          subspaceDim, found, gens, L, i, subV, currentM, currentN,
          GmodN, action, module, factors, factor, kernel, preImg,
          gensM, gensN, gensRel, mats, g, mat, row, j, elm, img,
          field, gensMmodN, basisMmodN;

    layerSize := Size(M) / Size(N);

    # If layer is small enough, no refinement needed
    if not LayerNeedsRefinement(layerSize) then
        return [M, N];
    fi;

    # M/N is elementary abelian p^d
    hom := SafeNaturalHomByNSG(M, N);
    if hom = fail then
        return [M, N];  # Can't form quotient; skip refinement
    fi;
    MmodN := ImagesSource(hom);

    # Check if it's a p-group first
    if not IsPGroup(MmodN) then
        return [M, N];  # Not a p-group, can't refine
    fi;

    # Determine p and d
    p := PrimePGroup(MmodN);
    if p = fail then
        return [M, N];  # Not a p-group, can't refine
    fi;
    dim := LogInt(layerSize, p);

    if dim <= 3 then
        return [M, N];  # Already small enough
    fi;

    refinement := [M];
    currentM := M;

    while Size(currentM) / Size(N) > p^3 do
        found := false;

        # METHOD 1: Try MeatAxe-style decomposition
        # View currentM/N as a GF(p)[G]-module and find composition factors
        if not found then
            hom := SafeNaturalHomByNSG(currentM, N);
            if hom <> fail then
                MmodN := ImagesSource(hom);
                if IsElementaryAbelian(MmodN) and Size(MmodN) > p^3 then
                    for L in MaximalSubgroups(MmodN) do
                        preImg := PreImages(hom, L);
                        if IsNormal(G, preImg) and Size(preImg) > Size(N) then
                            Add(refinement, preImg);
                            currentM := preImg;
                            found := true;
                            break;
                        fi;
                    od;
                fi;
            fi;
        fi;

        # METHOD 2: Try derived/lower central series (original approach)
        # NOTE: All methods must check IsSubgroup(L, N), not just Size(L) > Size(N).
        # For direct products on disjoint point sets, a subgroup can have the right
        # size range but not contain N (e.g., H81 on {7-18} vs V_4 on {3-6}).
        if not found then
            for L in DerivedSeriesOfGroup(currentM) do
                if Size(L) > Size(N) and Size(L) < Size(currentM)
                   and IsSubgroup(L, N) then
                    if IsNormal(G, L) then
                        Add(refinement, L);
                        currentM := L;
                        found := true;
                        break;
                    fi;
                fi;
            od;
        fi;

        if not found then
            for L in LowerCentralSeriesOfGroup(currentM) do
                if Size(L) > Size(N) and Size(L) < Size(currentM)
                   and IsSubgroup(L, N) then
                    if IsNormal(G, L) then
                        Add(refinement, L);
                        currentM := L;
                        found := true;
                        break;
                    fi;
                fi;
            od;
        fi;

        # METHOD 3: Try Frattini subgroup
        if not found then
            L := FrattiniSubgroup(currentM);
            if Size(L) > Size(N) and Size(L) < Size(currentM)
               and IsSubgroup(L, N) then
                if IsNormal(G, L) then
                    Add(refinement, L);
                    currentM := L;
                    found := true;
                fi;
            fi;
        fi;

        # METHOD 4: For permutation groups, try stabilizer chains
        if not found and IsPermGroup(G) then
            # Try taking intersection with stabilizers
            for i in MovedPoints(G) do
                L := Intersection(currentM, Stabilizer(G, i));
                if Size(L) > Size(N) and Size(L) < Size(currentM)
                   and IsSubgroup(L, N) then
                    if IsNormal(G, L) then
                        Add(refinement, L);
                        currentM := L;
                        found := true;
                        break;
                    fi;
                fi;
            od;
        fi;

        if not found then
            # If no refinement found, proceed with the large layer
            break;
        fi;
    od;

    Add(refinement, N);
    return refinement;
end;

###############################################################################
# CoprimePriorityChiefSeries(P, shifted_factors)
#
# For direct products P = G_1 x ... x G_k, reorder the chief series to
# process coprime layers (odd prime vs 2-part) FIRST. This minimizes the
# intermediate parent count during lifting.
#
# Mathematical justification: For P a direct product on disjoint orbits,
# each factor's chief series terms are normal in P (since conjugation by
# other factors acts trivially). Any interleaving of per-factor chief
# series layers gives a valid normal series with elementary abelian factors.
#
# Performance impact: Processing coprime layers first gives growth factor 1
# (Schur-Zassenhaus: unique complement class). This keeps the parent count
# low before hitting the "explosive" C_2 layers, reducing total work from
# O(c^n) to O(c^m * n) where m < n is the number of non-coprime layers.
###############################################################################

CoprimePriorityChiefSeries := function(P, shifted_factors)
    local k, factor_series, layers, current_level, num_layers_per_factor,
          total_layers, series, step, best_factor, best_priority,
          f, layer_size, p, priority, term_gens, i, refined,
          M, N, layerRefinement, j;

    k := Length(shifted_factors);

    if k <= 1 then
        # Single factor, no reordering possible
        return RefinedChiefSeries(P);
    fi;

    # Compute chief series for each shifted factor individually
    factor_series := List(shifted_factors, ChiefSeries);
    num_layers_per_factor := List(factor_series, s -> Length(s) - 1);
    total_layers := Sum(num_layers_per_factor);

    if total_layers = 0 then
        return [P, Group(())];
    fi;

    # Greedy merge: at each step, pick the factor whose next layer has
    # lowest expected growth (coprime first, then small layers)
    current_level := List([1..k], x -> 1);
    series := [P];

    for step in [1..total_layers] do
        best_factor := fail;
        best_priority := infinity;

        for f in [1..k] do
            if current_level[f] <= num_layers_per_factor[f] then
                layer_size := Size(factor_series[f][current_level[f]]) /
                              Size(factor_series[f][current_level[f] + 1]);

                if layer_size <= 1 then
                    # Trivial layer, process immediately
                    priority := -1;
                else
                    p := SmallestPrimeDivisor(layer_size);
                    # Priority: lower = process first
                    # Odd primes: typically coprime to the 2-group parts,
                    # giving growth = 1 via Schur-Zassenhaus
                    if p > 2 then
                        priority := 0;
                    elif layer_size = 2 then
                        # Single C_2: moderate growth
                        priority := 1;
                    else
                        # Larger 2-power layer (C_2^k): higher growth
                        priority := 1 + LogInt(layer_size, 2);
                    fi;
                fi;

                # Tie-break: prefer factors with fewer remaining layers
                # (finish short factors quickly to reduce cross-product size)
                if priority < best_priority or
                   (priority = best_priority and best_factor <> fail and
                    num_layers_per_factor[f] - current_level[f] <
                    num_layers_per_factor[best_factor] - current_level[best_factor]) then
                    best_priority := priority;
                    best_factor := f;
                fi;
            fi;
        od;

        if best_factor = fail then break; fi;

        # Advance this factor to its next chief series term
        current_level[best_factor] := current_level[best_factor] + 1;

        # Build series term: product of current level for each factor
        term_gens := [];
        for i in [1..k] do
            if current_level[i] <= Length(factor_series[i]) then
                Append(term_gens,
                    GeneratorsOfGroup(factor_series[i][current_level[i]]));
            fi;
        od;

        if Length(term_gens) > 0 then
            Add(series, Group(term_gens));
        else
            Add(series, Group(()));
        fi;
    od;

    # Refine any large layers (same as RefinedChiefSeries)
    refined := [series[1]];
    for i in [1..Length(series)-1] do
        M := series[i];
        N := series[i+1];
        layerRefinement := RefineChiefSeriesLayer(P, M, N);
        for j in [2..Length(layerRefinement)] do
            Add(refined, layerRefinement[j]);
        od;
    od;

    return refined;
end;

###############################################################################
# RefinedChiefSeries(P)
#
# Compute chief series and refine any layers that are too large.
###############################################################################

RefinedChiefSeries := function(P)
    local series, refined, i, M, N, layerRefinement, j;

    series := ChiefSeries(P);
    refined := [series[1]];

    for i in [1..Length(series)-1] do
        M := series[i];
        N := series[i+1];

        layerRefinement := RefineChiefSeriesLayer(P, M, N);

        # Add all intermediate subgroups (skip M which is already in refined)
        for j in [2..Length(layerRefinement)] do
            Add(refined, layerRefinement[j]);
        od;
    od;

    return refined;
end;

###############################################################################
# FindFPFByMaximalDescent(P, shifted_factors, offsets)
#
# Alternative algorithm for large products: descend through maximal subgroups
# with early pruning when projection onto any factor becomes non-surjective.
#
# More efficient than chief series lifting when |P| is very large or the
# chief series has many layers.
###############################################################################

FindFPFByMaximalDescent := function(P, shifted_factors, offsets)
    local fpfSubdirects, candidates, visited, H, maxSubs, M, isFPF,
          projOK, i, factor, offset, degree, moved, gens_proj, projection,
          sizeKey;

    fpfSubdirects := [];
    candidates := [P];
    visited := rec();

    while Length(candidates) > 0 do
        H := Remove(candidates);

        # Skip if already visited a group of this size (approximate dedup)
        sizeKey := String(Size(H));
        if IsBound(visited.(sizeKey)) then
            # Check if H is conjugate to any visited group of same size
            if ForAny(visited.(sizeKey), v -> RepresentativeAction(P, H, v) <> fail) then
                continue;
            fi;
        else
            visited.(sizeKey) := [];
        fi;
        Add(visited.(sizeKey), H);

        # Check if H is an FPF subdirect
        isFPF := IsFPFSubdirect(H, shifted_factors, offsets);

        if isFPF then
            # H is FPF subdirect - add it (will be deduplicated later)
            Add(fpfSubdirects, H);
        fi;

        # Check if we should descend further
        # Only descend if projections are still surjective
        projOK := true;
        for i in [1..Length(shifted_factors)] do
            factor := shifted_factors[i];
            offset := offsets[i];
            degree := NrMovedPoints(factor);
            moved := [offset+1..offset+degree];

            gens_proj := List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, moved));
            gens_proj := Filtered(gens_proj, g -> g <> ());

            if Length(gens_proj) = 0 then
                projOK := false;
                break;
            fi;

            projection := Group(gens_proj);

            # If projection is not surjective, no FPF subdirect can be found below H
            if Size(projection) < Size(factor) then
                projOK := false;
                break;
            fi;
        od;

        if not projOK then
            continue;  # Prune this branch
        fi;

        # Get maximal subgroups and add to candidates
        maxSubs := MaximalSubgroupClassReps(H);
        for M in maxSubs do
            # Quick filter: only consider if size is at least product of factor sizes
            # divided by index, which is necessary for FPF
            if Size(M) >= Size(H) / Minimum(List(shifted_factors, Size)) then
                Add(candidates, M);
            fi;
        od;
    od;

    return RemoveConjugatesUnderP(P, fpfSubdirects);
end;

###############################################################################
# ShouldUseMaximalDescent(P, series)
#
# Heuristic to decide whether to use maximal descent vs chief series lifting.
# Use maximal descent when:
# - |P| > 70,000 (catches [8,2] partition with |P|=80,640)
# - Chief series has > 8 layers (many lifting steps)
#
# Results verified correct against OEIS A000638 for S8-S11.
###############################################################################

ShouldUseMaximalDescent := function(P, series)
    # DISABLED: Always use chief series lifting.
    # Maximal descent enumerates the subgroup lattice top-down, which is
    # exponentially expensive for large groups. For S12+ where |P| is in
    # the millions, this is catastrophically slow.
    # Chief series lifting handles all cases correctly now that
    # NormalSubgroupsBetween has the IsSimpleGroup fast path for
    # non-abelian simple chief factors (e.g., A8 in [8,2] partition).
    return false;
end;

###############################################################################
###############################################################################
# _DeduplicateCCSbyConjugacy(fpfList, partNorm, P)
#
# For non-elementary-abelian P, deduplicates a list of P-conjugacy class
# representatives of FPF subgroups by computing orbits under the partition
# normalizer N using Union-Find.
#
# Algorithm: For each generator g of N, conjugate each P-class rep H_i by g,
# then find which P-class rep H_j is P-conjugate to H_i^g (using RA under P,
# which is much cheaper than RA under N). Union(i,j) in Union-Find.
# Final components = N-conjugacy classes.
#
# Complexity: O(|gens_N| * k * b * RA_P) instead of O(k^2 * RA_N)
# where k = |fpfList|, b = avg bucket size, RA_P << RA_N.
#
# Input: fpfList = list of P-class FPF representatives (from CCS)
#        partNorm = partition normalizer group N
#        P = direct product group (for P-conjugacy tests)
# Output: N-class representatives of FPF subgroups
###############################################################################

_DeduplicateCCSbyConjugacy := function(fpfList, partNorm, P)
    local n, parent, rnk, byInv, invKeys, i, inv, key,
          gens, g, Hg, keyg, j, idx, reps, roots, t0, t1,
          numBuckets, maxBucket, Find, Union;

    n := Length(fpfList);
    if n <= 1 then
        return fpfList;
    fi;

    t0 := Runtime();

    # Union-Find with path compression and union by rank
    parent := [1..n];
    rnk := List([1..n], x -> 0);

    Find := function(x)
        while parent[x] <> x do
            parent[x] := parent[parent[x]];  # path halving
            x := parent[x];
        od;
        return x;
    end;

    Union := function(x, y)
        local rx, ry;
        rx := Find(x); ry := Find(y);
        if rx = ry then return; fi;
        if rnk[rx] < rnk[ry] then
            parent[rx] := ry;
        elif rnk[rx] > rnk[ry] then
            parent[ry] := rx;
        else
            parent[ry] := rx;
            rnk[rx] := rnk[rx] + 1;
        fi;
    end;

    # Build invariant lookup: key -> list of indices
    # Use ComputeSubgroupInvariant (rich) for large inputs to get small buckets.
    # CheapSubgroupInvariant is insufficient for FPF subgroups where orbit sizes
    # are always identical (e.g., all [4,4,2,2,2,2]), causing bucket sizes of 1000+.
    byInv := rec();
    invKeys := [];  # invKeys[i] = key for fpfList[i]
    for i in [1..n] do
        if n > 5000 then
            inv := ComputeSubgroupInvariant(fpfList[i]);
        else
            inv := CheapSubgroupInvariant(fpfList[i]);
        fi;
        key := InvariantKey(inv);
        invKeys[i] := key;
        if not IsBound(byInv.(key)) then
            byInv.(key) := [];
        fi;
        Add(byInv.(key), i);
    od;

    t1 := Runtime();
    numBuckets := Length(RecNames(byInv));
    maxBucket := Maximum(List(RecNames(byInv), k -> Length(byInv.(k))));
    Print("    CCS dedup: ", n, " groups, ",
          numBuckets, " inv buckets (max ", maxBucket, "), ",
          Length(GeneratorsOfGroup(partNorm)), " norm gens",
          " (inv ", t1 - t0, "ms)\n");

    # For each generator of N, compute the action on P-class reps.
    # For each P-class rep H_i, compute H_i^g and find which P-class rep H_j
    # is P-conjugate to H_i^g. Union(i,j) identifies them in the same N-class.
    #
    # KEY OPTIMIZATION: Conjugation preserves ALL group-theoretic invariants
    # (Size, DerivedLength, Center, AbelianInvariants, ConjugacyClasses, etc.).
    # So invariant(H_i^g) = invariant(H_i). We use the CACHED key invKeys[i]
    # instead of recomputing the invariant for H_i^g.
    gens := GeneratorsOfGroup(partNorm);
    for g in gens do
        for i in [1..n] do
            Hg := ConjugateGroup(fpfList[i], g);
            # Use cached invariant key: conjugation preserves all invariants
            keyg := invKeys[i];
            if IsBound(byInv.(keyg)) then
                for idx in byInv.(keyg) do
                    # Test P-conjugacy (cheap: |P| << |N|)
                    if RepresentativeAction(P, Hg, fpfList[idx]) <> fail then
                        Union(i, idx);
                        break;
                    fi;
                od;
            fi;
        od;
    od;

    # Collect one representative per component
    reps := [];
    roots := [];
    for i in [1..n] do
        if Find(i) = i then
            Add(reps, fpfList[i]);
        fi;
    od;

    Print("    CCS dedup: ", n, " -> ", Length(reps),
          " (", Runtime() - t0, "ms)\n");

    return reps;
end;

###############################################################################
###############################################################################
# _DeduplicateEAFPFbyGF2Orbits(P, fpfList, partNorm)
#
# For elementary abelian P = C_p^d (typically C_2^d), deduplicates a list of
# FPF subgroups by computing orbits under the partition normalizer, using
# GF(p) linear algebra instead of pairwise RepresentativeAction.
#
# Algorithm:
# 1. Choose a Pcgs for P, giving GF(p)^d coordinates
# 2. Express each FPF subgroup as a RREF matrix over GF(p)
# 3. Compute the partition normalizer's action as GF(p) matrices
# 4. BFS on RREF matrices to find orbit representatives
# 5. Convert representatives back to permutation subgroups
#
# Complexity: O(|fpfList| * |gens(partNorm)|) vs O(|fpfList|^2) for pairwise
###############################################################################

_DeduplicateEAFPFbyGF2Orbits := function(P, fpfList, partNorm)
    local pcgs, dim, p, field, t0, t1, t2, normGens, mat, ii, jj, kk,
          conj, exps, actualNorm, intRow, rowInt,
          # Integer-packed representations
          intNormMats, actTables, xorTab, tab,
          intRREFs, intKeys, visited, reps, todo, todoHead,
          currRows, newRows, newKey, nBFS, nConvert,
          aa, bb, bit, val, gens_H,
          # Helper functions
          IntXOR, IntRREF, ApplyGen, RowsToKey, GF2VecToInt;

    t0 := Runtime();
    pcgs := Pcgs(P);
    dim := Length(pcgs);
    p := RelativeOrders(pcgs)[1];
    field := GF(p);

    if p <> 2 or dim > 16 then
        Print("  Integer BFS only for p=2 and dim<=16, skipping dedup\n");
        return fpfList;
    fi;

    # ==========================================
    # PRECOMPUTATION: XOR lookup table (256x256)
    # ==========================================
    xorTab := [];
    for aa in [0..255] do
        tab := [];
        for bb in [0..255] do
            val := 0;
            for bit in [0..7] do
                if (QuoInt(aa, 2^bit) mod 2) <> (QuoInt(bb, 2^bit) mod 2) then
                    val := val + 2^bit;
                fi;
            od;
            tab[bb+1] := val;
        od;
        xorTab[aa+1] := tab;
    od;

    # Inline XOR using lookup table
    IntXOR := function(a, b)
        if dim <= 8 then
            return xorTab[a+1][b+1];
        else
            # For dim > 8, split into low/high bytes
            return xorTab[(a mod 256)+1][(b mod 256)+1]
                 + 256 * xorTab[QuoInt(a,256)+1][QuoInt(b,256)+1];
        fi;
    end;

    # ==========================================
    # Step 1: Normalizer matrices in integer form
    # ==========================================
    actualNorm := Normalizer(partNorm, P);
    normGens := SmallGeneratingSet(actualNorm);

    intNormMats := [];
    for jj in [1..Length(normGens)] do
        mat := [];
        for ii in [1..dim] do
            conj := pcgs[ii] ^ normGens[jj];
            if not conj in P then
                mat := fail; break;
            fi;
            exps := ExponentsOfPcElement(pcgs, conj);
            if Length(exps) <> dim then
                mat := fail; break;
            fi;
            intRow := 0;
            for kk in [1..dim] do
                if exps[kk] mod 2 = 1 then intRow := intRow + 2^(kk-1); fi;
            od;
            Add(mat, intRow);
        od;
        if mat <> fail then
            Add(intNormMats, mat);
        fi;
    od;

    if Length(intNormMats) = 0 then
        Print("  GF(2) orbit dedup: no valid normalizer generators, skipping\n");
        return fpfList;
    fi;

    # ==========================================
    # PRECOMPUTATION: Action tables
    # For each generator g and each row integer r (0..2^dim-1),
    # actTables[g][r+1] = image of r under g (matrix multiply over GF(2)).
    # Image = XOR of genMatrix[i] for each bit i set in r.
    # ==========================================
    actTables := [];
    for jj in [1..Length(intNormMats)] do
        tab := [0];  # row 0 -> 0
        for rowInt in [1..2^dim - 1] do
            val := 0;
            for bit in [0..dim-1] do
                if QuoInt(rowInt, 2^bit) mod 2 = 1 then
                    val := IntXOR(val, intNormMats[jj][bit+1]);
                fi;
            od;
            tab[rowInt+1] := val;
        od;
        Add(actTables, tab);
    od;
    Print("  GF(2) orbit dedup (fast): dim=", dim, ", ", Length(actTables),
          " norm generators (from |Norm|=", Size(actualNorm), ")\n");
    Print("    Action tables precomputed (", 2^dim, " entries each)\n");

    # ==========================================
    # Helper: Integer RREF via Gaussian elimination with XOR
    # Input: list of integer rows
    # Output: sorted list of nonzero integer rows in RREF
    # ==========================================
    IntRREF := function(rows)
        local rr, nr, pivotCol, pivotIdx, i, mask, temp;
        rr := ShallowCopy(rows);
        nr := Length(rr);
        pivotIdx := 1;
        for pivotCol in [0..dim-1] do
            mask := 2^pivotCol;
            # Find pivot row
            temp := 0;
            for i in [pivotIdx..nr] do
                if QuoInt(rr[i], mask) mod 2 = 1 then
                    temp := i; break;
                fi;
            od;
            if temp = 0 then continue; fi;
            # Swap
            if temp <> pivotIdx then
                val := rr[pivotIdx]; rr[pivotIdx] := rr[temp]; rr[temp] := val;
            fi;
            # Eliminate from all other rows
            for i in [1..nr] do
                if i <> pivotIdx and QuoInt(rr[i], mask) mod 2 = 1 then
                    rr[i] := IntXOR(rr[i], rr[pivotIdx]);
                fi;
            od;
            pivotIdx := pivotIdx + 1;
            if pivotIdx > nr then break; fi;
        od;
        rr := Filtered(rr, x -> x > 0);
        Sort(rr);
        return rr;
    end;

    # ==========================================
    # Helper: Apply generator (via action table) to RREF rows
    # Returns RREF of the image
    # ==========================================
    ApplyGen := function(rows, genIdx)
        local newRows, r;
        newRows := List(rows, r -> actTables[genIdx][r+1]);
        return IntRREF(newRows);
    end;

    # ==========================================
    # Helper: Pack RREF rows into a single integer key
    # For dim<=8: each row is 0..255, pack as r1 + r2*256 + r3*256^2 + ...
    # For dim<=16: each row is 0..65535, pack with 65536 multiplier
    # Prepend row count to distinguish different dimensions
    # ==========================================
    RowsToKey := function(rows)
        local k, key, i, base;
        k := Length(rows);
        if k = 0 then return 0; fi;
        if dim <= 8 then
            base := 256;
        else
            base := 65536;
        fi;
        key := k;
        for i in [1..k] do
            key := key * base + rows[i];
        od;
        return key;
    end;

    # ==========================================
    # Helper: Convert GF(2) vector to integer
    # ==========================================
    GF2VecToInt := function(vec)
        local v, i;
        v := 0;
        for i in [1..dim] do
            if IsOne(vec[i]) then v := v + 2^(i-1); fi;
        od;
        return v;
    end;

    # ==========================================
    # Step 2: Convert all FPF subgroups to integer RREF + key
    # ==========================================
    intRREFs := [];
    intKeys := [];
    for ii in [1..Length(fpfList)] do
        gens_H := Pcgs(fpfList[ii]);
        if gens_H = fail then
            gens_H := GeneratorsOfGroup(fpfList[ii]);
        fi;
        if Length(gens_H) = 0 then
            Add(intRREFs, []);
            Add(intKeys, 0);
        else
            mat := List(gens_H, function(g)
                local e;
                e := ExponentsOfPcElement(pcgs, g);
                val := 0;
                for kk in [1..dim] do
                    if e[kk] mod 2 = 1 then val := val + 2^(kk-1); fi;
                od;
                return val;
            end);
            mat := IntRREF(mat);
            Add(intRREFs, mat);
            Add(intKeys, RowsToKey(mat));
        fi;
    od;
    t1 := Runtime();
    nConvert := t1 - t0;
    Print("    RREF conversion: ", Length(fpfList), " groups (", nConvert, "ms)\n");

    # ==========================================
    # Step 3: BFS orbit computation using integer keys
    # Use rec() hash table for O(1) amortized lookup/insertion.
    # NOTE: NewDictionary(0, true) creates DictionaryBySort with O(n)
    # insertion for large integer keys, giving O(n^2) total. Convert
    # integer keys to strings prefixed with "k" for valid rec() names.
    # ==========================================
    visited := rec();
    reps := [];
    nBFS := 0;
    for ii in [1..Length(intRREFs)] do
        newKey := Concatenation("k", String(intKeys[ii]));
        if not IsBound(visited.(newKey)) then
            visited.(newKey) := true;
            Add(reps, fpfList[ii]);
            # BFS: explore orbit under normalizer action tables
            todo := [intRREFs[ii]];
            todoHead := 1;
            while todoHead <= Length(todo) do
                currRows := todo[todoHead];
                todoHead := todoHead + 1;
                for jj in [1..Length(actTables)] do
                    if Length(currRows) > 0 then
                        newRows := ApplyGen(currRows, jj);
                    else
                        newRows := [];
                    fi;
                    newKey := Concatenation("k", String(RowsToKey(newRows)));
                    nBFS := nBFS + 1;
                    if not IsBound(visited.(newKey)) then
                        visited.(newKey) := true;
                        Add(todo, newRows);
                    fi;
                od;
                if todoHead mod 50000 = 0 then
                    Print("    BFS progress: ", todoHead, "/", Length(todo),
                          " processed, ", Length(reps), " orbits so far (",
                          Runtime() - t1, "ms)\n");
                fi;
            od;
        fi;
        # Progress for outer loop
        if ii mod 50000 = 0 then
            Print("    BFS outer: ", ii, "/", Length(fpfList),
                  " checked, ", Length(reps), " orbits, ", nBFS,
                  " BFS steps (", Runtime() - t1, "ms)\n");
        fi;
    od;

    t2 := Runtime();
    Print("    BFS: ", nBFS, " iterations, ", Length(fpfList), " -> ", Length(reps),
          " classes (", t2 - t1, "ms)\n");
    Print("  GF(2) orbit dedup total: ", Length(fpfList), " -> ", Length(reps),
          " classes (", t2 - t0, "ms)\n");

    return reps;
end;


###############################################################################
# _GoursatBuildFiberProduct(T1, T2, hom1, hom2, phi, pts1, pts2)
#
# Build the fiber product H = {(a,b) in T1 x T2 : phi(hom1(a)) = hom2(b)}
# where T1 acts on pts1, T2 acts on pts2 (disjoint point sets).
#
# The group H is generated by:
#   - For each generator g of T1: g * PreImagesRepresentative(hom2, Image(phi, Image(hom1, g)))
#   - For each generator n of Kernel(hom2): n
#
# Returns: the fiber product as a permutation group on pts1 union pts2,
#          or fail if construction fails.
#
# Named with underscore prefix to avoid collision with BuildFiberProduct in
# lifting_method_fast_v2.g (the C2 fiber product optimization).
###############################################################################
_GoursatBuildFiberProduct := function(T1, T2, hom1, hom2, phi, pts1, pts2)
    local gens, g, img_q, preimg, kerGens, n, H, expectedOrder;

    gens := [];

    # For each generator of T1, find matching element of T2
    for g in GeneratorsOfGroup(T1) do
        img_q := Image(phi, Image(hom1, g));
        preimg := PreImagesRepresentative(hom2, img_q);
        Add(gens, g * preimg);
    od;

    # Add kernel of hom2 (elements of T2 mapping to identity in Q2)
    kerGens := GeneratorsOfGroup(Kernel(hom2));
    for n in kerGens do
        Add(gens, n);
    od;

    # Remove trivial generators
    gens := Filtered(gens, g -> g <> ());
    if Length(gens) = 0 then
        H := Group(());
    else
        H := Group(gens);
    fi;

    # Verify order: |H| = |Ker(hom1)| * |T2| = |N1| * |T2|
    # Equivalently |H| = |T1| * |N2| / 1 ... actually |H| = |N1| * |T2| = |T1| * |N2|
    # since |T1|/|N1| = |Q| = |T2|/|N2|
    expectedOrder := Size(Kernel(hom1)) * Size(T2);
    if Size(H) <> expectedOrder then
        Print("    WARNING: Fiber product order mismatch: got ", Size(H),
              " expected ", expectedOrder, "\n");
        return fail;
    fi;

    return H;
end;


###############################################################################
# GoursatFPFSubdirects(T1, T2, pts1, pts2)
#
# Enumerate all FPF subdirect products of T1 x T2 using Goursat's lemma.
#
# Goursat's lemma: Every subdirect product of T1 x T2 corresponds to a triple
# (N1, N2, phi) where N1 <| T1, N2 <| T2, and phi: T1/N1 -> T2/N2 is an
# isomorphism. Two triples (N1, N2, phi) and (N1, N2, phi') give P-conjugate
# fiber products iff phi and phi' differ by an inner automorphism of the
# quotient induced by T1 or T2.
#
# P-class representatives correspond to double cosets:
#   Inn_{T2}(Q) \ Iso(Q1, Q2) / Inn_{T1}(Q)
# which equals:
#   innT2_transported \ Aut(Q1) / innT1_Q
#
# Returns: List of P-class representatives of FPF subdirect products
###############################################################################
GoursatFPFSubdirects := function(T1, T2, pts1, pts2)
    local normals1, normals2, N1, N2, hom1, hom2, Q1, Q2, iso,
          autQ, innT1_Q, innT2_Q, dcosets, dc, alpha, phi,
          H, results, orbits, t0, sizeQ,
          g, img_in_aut, gens_innT1, gens_innT2, allPts;

    t0 := Runtime();
    normals1 := NormalSubgroups(T1);
    normals2 := NormalSubgroups(T2);

    # Guard: if either factor has too many normals, Goursat produces
    # too many fiber products for efficient dedup. Fall back to lifting.
    if Length(normals1) > 50 or Length(normals2) > 50 then
        Print("  Goursat SKIPPED: too many normals (", Length(normals1),
              "x", Length(normals2), "), falling back to lifting\n");
        return fail;
    fi;

    results := [];
    orbits := [pts1, pts2];
    allPts := Union(pts1, pts2);

    for N1 in normals1 do
        for N2 in normals2 do
            # Quotients must have same size
            if Size(T1) / Size(N1) <> Size(T2) / Size(N2) then
                continue;
            fi;

            sizeQ := Size(T1) / Size(N1);

            # Trivial quotient: fiber product = full product T1 x T2
            if sizeQ = 1 then
                # Full product: FPF iff each factor is transitive on its points
                # (which it always is since T1, T2 are transitive)
                # But the full product P is always added by the caller, so skip
                # Actually, we should still check and include it
                H := Group(Concatenation(
                    GeneratorsOfGroup(T1), GeneratorsOfGroup(T2)));
                if ForAll(orbits, orb -> IsTransitive(H, orb)) then
                    Add(results, H);
                fi;
                continue;
            fi;

            # Compute quotient homomorphisms
            hom1 := SafeNaturalHomByNSG(T1, N1);
            if hom1 = fail then continue; fi;
            hom2 := SafeNaturalHomByNSG(T2, N2);
            if hom2 = fail then continue; fi;

            Q1 := Image(hom1);
            Q2 := Image(hom2);

            # Check if quotients are isomorphic
            iso := IsomorphismGroups(Q1, Q2);
            if iso = fail then continue; fi;

            # For quotient of order 2, there's only one isomorphism
            # (Aut(C_2) is trivial), so exactly one fiber product
            if sizeQ = 2 then
                H := _GoursatBuildFiberProduct(T1, T2, hom1, hom2, iso, pts1, pts2);
                if H <> fail and ForAll(orbits, orb -> IsTransitive(H, orb)) then
                    Add(results, H);
                fi;
                continue;
            fi;

            # General case: enumerate double coset representatives
            # Inn_{T1}(Q1): automorphisms of Q1 induced by conjugation in T1
            autQ := AutomorphismGroup(Q1);

            gens_innT1 := [];
            for g in GeneratorsOfGroup(T1) do
                img_in_aut := ConjugatorAutomorphismNC(Q1, Image(hom1, g));
                Add(gens_innT1, img_in_aut);
            od;
            gens_innT1 := Filtered(gens_innT1, a -> a <> IdentityMapping(Q1));
            if Length(gens_innT1) = 0 then
                innT1_Q := TrivialSubgroup(autQ);
            else
                innT1_Q := SubgroupNC(autQ, gens_innT1);
            fi;

            # Inn_{T2}(Q2) transported to Aut(Q1) via iso:
            # For t2 in T2, conj_{hom2(t2)} in Aut(Q2).
            # Transport to Aut(Q1): alpha -> iso^-1 * conj_{hom2(t2)} * iso
            gens_innT2 := [];
            for g in GeneratorsOfGroup(T2) do
                img_in_aut := CompositionMapping(
                    InverseGeneralMapping(iso),
                    CompositionMapping(
                        ConjugatorAutomorphismNC(Q2, Image(hom2, g)),
                        iso
                    )
                );
                Add(gens_innT2, img_in_aut);
            od;
            gens_innT2 := Filtered(gens_innT2, a -> a <> IdentityMapping(Q1));
            if Length(gens_innT2) = 0 then
                innT2_Q := TrivialSubgroup(autQ);
            else
                innT2_Q := SubgroupNC(autQ, gens_innT2);
            fi;

            # Double cosets: innT2_Q \ autQ / innT1_Q
            dcosets := DoubleCosets(autQ, innT2_Q, innT1_Q);

            for dc in dcosets do
                alpha := Representative(dc);
                # phi = iso * alpha (apply alpha first, then iso)
                # Actually: we want phi: Q1 -> Q2 such that
                # the fiber product uses phi. Different alphas give
                # non-P-conjugate fiber products.
                # phi = alpha * iso (apply alpha to Q1, then iso to Q2)
                # Wait - alpha is in Aut(Q1), so alpha: Q1 -> Q1
                # We want phi: Q1 -> Q2, so phi = alpha * iso
                # (first apply alpha in Q1, then iso to Q2)
                if IsOne(alpha) then
                    phi := iso;
                else
                    phi := CompositionMapping(iso, alpha);
                fi;

                H := _GoursatBuildFiberProduct(T1, T2, hom1, hom2, phi, pts1, pts2);
                if H <> fail and ForAll(orbits, orb -> IsTransitive(H, orb)) then
                    Add(results, H);
                fi;
            od;
        od;
    od;

    Print("  Goursat fast path: |T1|=", Size(T1), " |T2|=", Size(T2),
          ", ", Length(normals1), "x", Length(normals2), " normal pairs -> ",
          Length(results), " FPF subdirects (",
          Runtime() - t0, "ms)\n");

    return results;
end;


###############################################################################
# Inter-layer deduplication for lifting.
# Removes norm-conjugates from intermediate results between chief series layers.
# Prevents exponential blowup when C_2 layers produce many complements that are
# conjugate under the partition normalizer.
#
# Mathematical justification: if H1^n = H2 for n in outerNormForLayer[i]
# (which stabilizes series[i+1]...series[k+1]), then complements of
# series[j]/series[j+1] in H1 biject with complements in H2 via conjugation
# by n. So keeping one representative per n-orbit at layer i yields exactly
# the right set of representatives at the final layer.
###############################################################################

# OPTION B: richer inter-layer invariant.
# Use Center size, DerivedSubgroup size, and Exponent as extra discriminators.
# These are O(1) amortized (GAP caches them) and cheap to compute.
# Element order histogram is skipped here — it requires element iteration
# which is O(|H|) and can be slow at intermediate layers with many groups.
USE_RICH_INTERLAYER_INV := true;

_InterLayerInvariantKey := function(H, degree)
    local orbSizes;
    orbSizes := SortedList(List(Orbits(H, [1..degree]), Length));
    if USE_RICH_INTERLAYER_INV then
        return String([Size(H), orbSizes, AbelianInvariants(H),
                       DerivedLength(H), Size(Center(H)),
                       Size(DerivedSubgroup(H)), Exponent(H)]);
    else
        return String([Size(H), orbSizes, AbelianInvariants(H),
                       DerivedLength(H)]);
    fi;
end;

_InterLayerDedup := function(groups, norm, degree)
    local byInv, unique, H, key, isDupe, K, t0, before,
          maxBucket, totalChecked, totalFound;

    t0 := Runtime();
    before := Length(groups);
    byInv := rec();
    unique := [];
    # Option B: modest maxBucket bump when using rich invariants.
    if USE_RICH_INTERLAYER_INV then
        maxBucket := 50;
    else
        maxBucket := 20;
    fi;
    totalChecked := 0;
    totalFound := 0;

    for H in groups do
        key := _InterLayerInvariantKey(H, degree);
        if not IsBound(byInv.(key)) then
            byInv.(key) := [];
        fi;

        isDupe := false;
        if Length(byInv.(key)) < maxBucket then
            for K in byInv.(key) do
                totalChecked := totalChecked + 1;
                if RepresentativeAction(norm, K, H) <> fail then
                    isDupe := true;
                    totalFound := totalFound + 1;
                    break;
                fi;
            od;
        fi;

        if not isDupe then
            Add(byInv.(key), H);
            Add(unique, H);
        fi;

        # Early exit: only apply when NOT using rich invariants
        # (with rich invariants we trust that remaining work is bounded by bucket size)
        if not USE_RICH_INTERLAYER_INV and totalChecked >= 200 and totalFound = 0 then
            Append(unique, groups{[Position(groups, H)+1..Length(groups)]});
            Print("    Inter-layer dedup: ", before, " -> ", Length(unique),
                  " (early exit after ", totalChecked, " checks, ",
                  Runtime() - t0, "ms)\n");
            return unique;
        fi;
    od;

    Print("    Inter-layer dedup: ", before, " -> ", Length(unique),
          " (", Runtime() - t0, "ms, ", totalChecked, " RA, ",
          totalFound, " dups)\n");
    return unique;
end;


# _SnFastPathFPFSubdirects(Sn_factor, n_Sn, rest_subdirects)
#
# For each K in rest_subdirects (a subdirect product of the "rest" factors,
# acting on points AFTER the S_n block), enumerate all Goursat subdirect
# products of S_n x K.
#
# Uses the fact that S_n (n >= 5) has only 3 normal subgroups: {1}, A_n, S_n.
# For each normal subgroup N_K of K:
#   - If K/N_K is trivial: gives the full product S_n x K
#   - If K/N_K = C_2: gives the diagonal {(s,k) : sgn(s)=0 iff k in N_K}
#   - If K/N_K = S_n (rare): skip for now (would need explicit iso)
#
# Returns: list of generating sets (as perm groups) for each subdirect product.
###############################################################################

_SnFastPathFPFSubdirects := function(Sn_factor, n_Sn, rest_subdirects)
    local results, K, An_gens, odd_perm, nsK, N, Q_size, k_outside,
          diag_gens, diag, full_prod, sn_moved;

    results := [];

    # Precompute A_n generators and one odd permutation for S_n.
    # Sn_factor lives on MovedPoints(Sn_factor), not [1..n_Sn], so An_gens
    # and odd_perm must be on the SAME shifted points — otherwise the
    # diagonal generators spill onto whichever block owns [1..n_Sn] and
    # leave the S_n block with trivial projection (bogus FPF group).
    sn_moved := MovedPoints(Sn_factor);
    An_gens := GeneratorsOfGroup(AlternatingGroup(sn_moved));
    odd_perm := (sn_moved[1], sn_moved[2]);

    for K in rest_subdirects do
        # Case 1: full product S_n x K (always present)
        full_prod := Group(Concatenation(GeneratorsOfGroup(Sn_factor),
                                          GeneratorsOfGroup(K)));
        Add(results, full_prod);

        # Case 2: For each N ⊲ K with |K/N| = 2, build the diagonal
        nsK := NormalSubgroups(K);
        for N in nsK do
            Q_size := Size(K) / Size(N);
            if Q_size = 2 then
                # Find an element of K outside N (representative of non-trivial coset)
                k_outside := First(GeneratorsOfGroup(K), g -> not g in N);
                if k_outside = fail then
                    k_outside := First(Elements(K), g -> not g in N);
                fi;
                if k_outside = fail then continue; fi;
                # Diagonal generators:
                #   A_n generators (sign = 0, so must pair with elements in N)
                #   N generators (in N, so must pair with even S_n elements)
                #   (odd, k_outside): one off-diagonal pair
                diag_gens := [];
                Append(diag_gens, An_gens);
                Append(diag_gens, GeneratorsOfGroup(N));
                Add(diag_gens, odd_perm * k_outside);
                diag := Group(diag_gens);
                Add(results, diag);
            fi;
        od;
    od;

    return results;
end;

###############################################################################
###############################################################################
# _GoursatGlueGeneral(K, G, nsK, nsG, normArg)
#
# Enumerate all Goursat subdirect products of K x G (on disjoint point sets).
# For each compatible pair (N_K, N_G) with K/N_K ≅ G/N_G, and for each
# isomorphism phi (from Aut(Q)), build the subdirect product.
#
# normArg is accepted but currently unused (reserved for future local dedup).
###############################################################################
_GoursatGlueGeneral := function(K, G, nsK, nsG, normArg)
    local results, N_K, N_G, Q_K_size, hom_K, hom_G, Q_K, Q_G, iso,
          aut_group, a, phi, gens, gen_K, coset_K, target_coset, g_rep;
    results := [];
    for N_K in nsK do
        Q_K_size := Size(K) / Size(N_K);
        hom_K := NaturalHomomorphismByNormalSubgroup(K, N_K);
        Q_K := ImagesSource(hom_K);
        for N_G in nsG do
            if Size(G) / Size(N_G) <> Q_K_size then continue; fi;
            hom_G := NaturalHomomorphismByNormalSubgroup(G, N_G);
            Q_G := ImagesSource(hom_G);
            iso := IsomorphismGroups(Q_K, Q_G);
            if iso = fail then continue; fi;
            if Q_K_size = 1 then
                gens := Concatenation(GeneratorsOfGroup(K),
                                      GeneratorsOfGroup(G));
                Add(results, Group(gens));
            else
                aut_group := AutomorphismGroup(Q_K);
                for a in aut_group do
                    phi := a * iso;
                    gens := [];
                    Append(gens, GeneratorsOfGroup(N_K));
                    Append(gens, GeneratorsOfGroup(N_G));
                    for gen_K in GeneratorsOfGroup(K) do
                        coset_K := Image(hom_K, gen_K);
                        target_coset := Image(phi, coset_K);
                        g_rep := PreImagesRepresentative(hom_G, target_coset);
                        Add(gens, gen_K * g_rep);
                    od;
                    Add(results, Group(gens));
                od;
            fi;
        od;
    od;
    return results;
end;

###############################################################################
# FindFPFClassesByLifting(P, shifted_factors, offsets)
#
# Main entry point: Find all FPF subdirect products of P by lifting
# through the chief series.
#
# Returns: List of representatives of P-conjugacy classes of FPF subdirects
###############################################################################

FindFPFClassesByLifting := function(P, shifted_factors, offsets, partNormalizer...)
    local series, current, i, M, N, layerSize, normArg, t0_layer, numLayers,
          allSubs, fpf, orbits, t0_fast, ccs, cc, H, outerNormForLayer;

    # partNormalizer is optional - extract from varargs
    if Length(partNormalizer) > 0 then
        normArg := partNormalizer[1];
    else
        normArg := fail;
    fi;

    # FAST PATH 1: For small ABELIAN direct products, enumerate all subgroups
    # directly instead of layer-by-layer lifting. This avoids exponential
    # blowup when all chief layers have 100% FPF acceptance (e.g., C_2^8 =
    # V_4^4 combos produce 8 C_2 layers each multiplying parents by ~14x).
    if IsAbelian(P) and Size(P) <= 256 then
        t0_fast := Runtime();
        orbits := List(shifted_factors, G -> MovedPoints(G));
        allSubs := AllSubgroups(P);
        fpf := Filtered(allSubs, function(H)
            return ForAll(orbits, function(orb)
                return IsTransitive(H, orb);
            end);
        end);
        Print("  SmallGroup fast path: |P|=", Size(P), ", ",
              Length(allSubs), " subgroups -> ", Length(fpf), " FPF (",
              Runtime() - t0_fast, "ms)\n");

        # Free allSubs to reclaim memory before BFS (417K group objects ~ 3-4GB)
        Unbind(allSubs);
        GASMAN("collect");

        # GF(2) ORBIT DEDUP: For elementary abelian P with many FPF subgroups,
        # dedup using orbit computation on GF(2) subspaces under the partition
        # normalizer. This replaces O(N^2) incrementalDedup with O(N * |gens|)
        # BFS on RREF matrices, which is orders of magnitude faster for N > 1000.
        if IsElementaryAbelian(P) and Length(fpf) > 500 and normArg <> fail then
            fpf := _DeduplicateEAFPFbyGF2Orbits(P, fpf, normArg);
        fi;

        return fpf;
    fi;

    # FAST PATH 2: CCS for very small non-abelian P.
    # Only for |P| <= 48: above this, CCS dedup can be very slow
    # (e.g., |P|=64 with D_4 x D_4 gives 681 classes, 46s dedup).
    # At |P| <= 48, CCS is always fast (<1s).
    if not IsAbelian(P) and Size(P) <= 48 then
        t0_fast := Runtime();
        ccs := ConjugacyClassesSubgroups(P);
        fpf := [];
        for cc in ccs do
            H := Representative(cc);
            if IsFPFSubdirect(H, shifted_factors, offsets) then
                Add(fpf, H);
            fi;
        od;
        Print("  CCS fast path: |P|=", Size(P), ", ",
              Length(ccs), " classes -> ",
              Length(fpf), " FPF reps (",
              Runtime() - t0_fast, "ms)\n");

        # Dedup P-class reps under partition normalizer to get N-class reps
        if normArg <> fail and Length(fpf) > 1 then
            fpf := _DeduplicateCCSbyConjugacy(fpf, normArg, P);
        fi;

        return fpf;
    fi;

    # FAST PATH 3: Goursat's lemma for 2-factor non-abelian products.
    # For 2-part partitions, Goursat directly enumerates subdirect products
    # via (N1, N2, phi) triples with double coset representatives, producing
    # dramatically fewer candidates than lifting (e.g., A_8 x A_8 -> 3 results
    # vs hours of lifting). Gated on non-abelian since abelian is handled above.
    if Length(shifted_factors) = 2 and not IsAbelian(P) then
        t0_fast := Runtime();
        fpf := GoursatFPFSubdirects(
            shifted_factors[1], shifted_factors[2],
            MovedPoints(shifted_factors[1]),
            MovedPoints(shifted_factors[2])
        );
        # fail means too many normals — fall through to lifting
        if fpf <> fail then
            return fpf;
        fi;
    fi;

    # FAST PATH 4: S_n short-circuit (n >= 5).
    # When any factor is S_n for n >= 5, the expensive non-solvable complement
    # path (Aut(A_n) reduction) dominates runtime. But S_n has only 3 normal
    # subgroups, so we can use Goursat directly: recursively enumerate subdirect
    # products of the "rest" factors, then glue each with S_n via the sign map.
    if Length(shifted_factors) >= 3 then
        fpf := CallFuncList(function()
            local sn_idx, sn_factor, rest_factors, rest_offsets, rest_product,
                  rest_subdirects, t0_sn, results, sn_moved, rest_points,
                  rest_P, i, K, N, sn_factorial, has_sn_quotient;
            sn_idx := fail;
            for i in [1..Length(shifted_factors)] do
                if NrMovedPoints(shifted_factors[i]) >= 5 and
                   IsNaturalSymmetricGroup(shifted_factors[i]) then
                    sn_idx := i;
                    break;
                fi;
            od;
            if sn_idx = fail then return fail; fi;
            t0_fast := Runtime();
            sn_factor := shifted_factors[sn_idx];
            sn_moved := MovedPoints(sn_factor);
            rest_factors := Concatenation(
                shifted_factors{[1..sn_idx-1]},
                shifted_factors{[sn_idx+1..Length(shifted_factors)]});
            rest_offsets := Concatenation(
                offsets{[1..sn_idx-1]},
                offsets{[sn_idx+1..Length(offsets)]});
            # Build rest product P
            rest_P := Group(Concatenation(List(rest_factors,
                GeneratorsOfGroup)));
            # Recursively enumerate subdirect products of rest
            rest_subdirects := FindFPFClassesByLifting(
                rest_P, rest_factors, rest_offsets);
            if rest_subdirects = fail then return fail; fi;

            # NARROW FIX: _SnFastPathFPFSubdirects does not handle the
            # K/N = S_n quotient case (see the "skip for now" comment in
            # its header). If any rest subdirect has a normal N with
            # [K:N] = n!, a full-iso S_n diagonal would be silently dropped
            # by the fast path. Bail to lifting in that case.
            #
            # Regression example: partition [10,6,2] with factors
            # TG(10,32) (S_6 on 10 pts) x TG(6,16) (natural S_6) x TG(2,1).
            # T_10 x T_2 has a rest subdirect with T_10 = S_6 quotient;
            # full-iso S_6 ↔ S_6 diagonals (2 extra classes) were missed.
            sn_factorial := Factorial(Length(sn_moved));
            has_sn_quotient := false;
            for K in rest_subdirects do
                if has_sn_quotient then break; fi;
                if Size(K) mod sn_factorial = 0 then
                    for N in NormalSubgroups(K) do
                        if Size(K) / Size(N) = sn_factorial then
                            has_sn_quotient := true;
                            break;
                        fi;
                    od;
                fi;
            od;
            if has_sn_quotient then
                Print("  S_n fast path: |rest|=", Length(rest_factors),
                      " factors, ", Length(rest_subdirects),
                      " rest subdirects -- rest has S_n-order quotient, falling back to lifting\n");
                return fail;
            fi;

            Print("  S_n fast path: |rest|=", Length(rest_factors),
                  " factors, ", Length(rest_subdirects), " rest subdirects, ");
            # Glue each rest subdirect with S_n via Goursat
            results := _SnFastPathFPFSubdirects(sn_factor,
                Length(sn_moved), rest_subdirects);
            Print(Length(results), " total (",
                  Runtime() - t0_fast, "ms)\n");
            return results;
        end, []);
        if fpf <> fail then
            return fpf;
        fi;
    fi;

    # FAST PATH 5: D_4^3 cache for combos with 3+ TG(4,3) factors.
    # When the combo contains 3+ copies of D_4 = TG(4,3), use the precomputed
    # D_4^3 cache (264 N-orbit reps) + Goursat gluing with the rest.
    # This avoids the exponential complement explosion in D_4^k chief series.
    if Length(shifted_factors) >= 3 and IsBound(D4_CUBE_CACHE) then
        fpf := CallFuncList(function()
            local d4_indices, rest_indices, n_d4, d4_factors, rest_factors,
                  rest_offsets, rest_P, rest_subdirects, rest_nsubs,
                  cacheGroups, results, K, Kprime, nsK, nsKprime,
                  t0_d4, i, N_rest, rest_NReps,
                  d4_offsets, remap, p, blk, pos_in_blk, g, img, shiftedGens;
            # Find D_4 = TG(4,3) factors
            d4_indices := Filtered([1..Length(shifted_factors)], i ->
                NrMovedPoints(shifted_factors[i]) = 4 and
                TransitiveIdentification(shifted_factors[i]) = 3);
            n_d4 := Length(d4_indices);
            if n_d4 < 3 then return fail; fi;
            # Use first 3 D_4 factors for the cache; any extras go into "rest"
            # (glued back in via Goursat, like any other non-cache factor).
            t0_fast := Runtime();
            # Use only first 3 D_4 indices for cache
            d4_indices := d4_indices{[1..3]};
            # Rest = everything not in d4_indices (non-D_4 factors + extra D_4s)
            rest_indices := Filtered([1..Length(shifted_factors)],
                i -> not i in d4_indices);

            # Build remapping from cache domain [1..12] to actual D_4 offsets.
            # Cache assumes D_4 factors at offsets [0, 4, 8].
            # Actual offsets come from offsets{d4_indices}.
            d4_offsets := offsets{d4_indices};
            remap := [];
            for p in [1..12] do
                blk := QuoInt(p - 1, 4) + 1;        # which D_4 block (1,2,3)
                pos_in_blk := (p - 1) mod 4 + 1;     # position within block
                remap[p] := d4_offsets[blk] + pos_in_blk;
            od;

            if Length(rest_indices) = 0 then
                # Pure D_4^3: remap cache to actual offsets
                if remap = [1..12] then
                    cacheGroups := List(D4_CUBE_CACHE, gens -> Group(gens));
                else
                    cacheGroups := List(D4_CUBE_CACHE, function(gens)
                        local shifted_gens, g, img, maxPt, p;
                        maxPt := Maximum(remap);
                        shifted_gens := [];
                        for g in gens do
                            img := [1..maxPt];
                            for p in [1..12] do
                                img[remap[p]] := remap[p^g];
                            od;
                            Add(shifted_gens, PermList(img));
                        od;
                        return Group(shifted_gens);
                    end);
                fi;
                Print("  D_4^3 cache fast path: ", Length(cacheGroups),
                      " reps (", Runtime() - t0_fast, "ms)\n");
                return cacheGroups;
            fi;
            rest_factors := shifted_factors{rest_indices};
            rest_offsets := offsets{rest_indices};
            # Enumerate subdirect products of the rest
            rest_P := Group(Concatenation(List(rest_factors,
                GeneratorsOfGroup)));
            rest_subdirects := FindFPFClassesByLifting(
                rest_P, rest_factors, rest_offsets);
            # Dedup rest subdirects under their normalizer
            N_rest := BuildPerComboNormalizer(
                List(rest_factors, NrMovedPoints), rest_factors,
                Maximum(List(rest_factors, f -> Maximum(MovedPoints(f)))));
            rest_NReps := [];
            for Kprime in rest_subdirects do
                found := false;
                for K in rest_NReps do
                    if Size(K) = Size(Kprime) and
                       RepresentativeAction(N_rest, Kprime, K) <> fail then
                        found := true; break;
                    fi;
                od;
                if not found then Add(rest_NReps, Kprime); fi;
            od;
            Print("  D_4^3 fast path: ", Length(rest_NReps),
                  " rest subdirects (sizes: ",
                  List(rest_NReps, Size), ")\n");
            # Load D_4^3 cache, remapped to actual offsets
            cacheGroups := List(D4_CUBE_CACHE, function(gens)
                local shifted_gens, g, img, maxPt, p;
                maxPt := Maximum(remap);
                shifted_gens := [];
                for g in gens do
                    img := [1..maxPt];
                    for p in [1..12] do
                        img[remap[p]] := remap[p^g];
                    od;
                    Add(shifted_gens, PermList(img));
                od;
                return Group(shifted_gens);
            end);
            # Pre-compute NormalSubgroups for rest factors (avoid redundant calls)
            rest_nsubs := List(rest_NReps, Kp -> NormalSubgroups(Kp));
            # Goursat glue each (K in cache, K' in rest subdirects)
            # with local per-pair dedup using normArg
            results := [];
            for i in [1..Length(cacheGroups)] do
                K := cacheGroups[i];
                nsK := NormalSubgroups(K);
                for j in [1..Length(rest_NReps)] do
                    Kprime := rest_NReps[j];
                    nsKprime := rest_nsubs[j];
                    Append(results,
                        _GoursatGlueGeneral(K, Kprime, nsK, nsKprime,
                                             normArg));
                od;
                if i mod 25 = 0 then
                    Print("  D_4^3 cache ", i, "/", Length(cacheGroups),
                          ": ", Length(results), " candidates so far (",
                          Int((Runtime() - t0_fast)/1000), "s)\n");
                fi;
            od;
            Print("  D_4^3 fast path: ", Length(results),
                  " candidates (", Int((Runtime() - t0_fast)/1000), "s)\n");
            return results;
        end, []);
        if fpf <> fail then
            return fpf;
        fi;
    fi;

    # Compute chief series with coprime-first reordering for direct products.
    # For multi-factor products (k >= 2), reorder to process odd-prime (coprime)
    # layers first — these have growth factor 1 (Schur-Zassenhaus), keeping
    # the intermediate parent count low before hitting the C_2 layers.
    if Length(shifted_factors) >= 2 then
        series := CoprimePriorityChiefSeries(P, shifted_factors);
    else
        series := RefinedChiefSeries(P);
    fi;
    numLayers := Length(series) - 1;

    # For very large products or complex chief series, use maximal descent
    if ShouldUseMaximalDescent(P, series) then
        return FindFPFByMaximalDescent(P, shifted_factors, offsets);
    fi;

    # Phase C1: Precompute per-layer outer normalizer bases.
    # At layer i, we can safely use normalizer elements that preserve ALL
    # remaining chief series members series[i+1], ..., series[k+1].
    # Without this restriction, an element n identifying C1 ~ C2 at layer i
    # might map series[i+1] to a different normal subgroup of P, causing
    # the lifts through layer i+1 to diverge (not be n-conjugate).
    # Build bottom-up: outerNormForLayer[numLayers] = full normArg (last layer
    # has no subsequent layers), then intersect with normalizers going up.
    if normArg <> fail then
        outerNormForLayer := [];
        outerNormForLayer[numLayers] := normArg;
        for i in [numLayers-1, numLayers-2..1] do
            outerNormForLayer[i] := Normalizer(outerNormForLayer[i+1], series[i+1]);
        od;
    fi;

    # Start with P itself
    current := [P];

    # Work down through each layer
    for i in [1..numLayers] do
        M := series[i];
        N := series[i+1];
        layerSize := Size(M) / Size(N);

        if Length(current) > 20 or numLayers > 3 then
            Print("    >> Layer ", i, "/", numLayers, ": |M/N|=", layerSize,
                  ", ", Length(current), " parents\n");
            if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
                PrintTo(_HEARTBEAT_FILE, "alive ",
                        Int(Runtime() / 1000), "s ",
                        _CURRENT_COMBO, " layer ", i, "/",
                        numLayers, " |M/N|=", layerSize, " ",
                        Length(current), " parents\n");
            fi;
        fi;

        t0_layer := Runtime();

        # Phase C1: Use per-layer stabilizer (or fail if no partition normalizer)
        if normArg <> fail then
            current := LiftThroughLayer(P, M, N, current, shifted_factors, offsets, outerNormForLayer[i]);
        else
            current := LiftThroughLayer(P, M, N, current, shifted_factors, offsets, fail);
        fi;

        # Early termination: if no candidates survived this layer, none will appear later
        if Length(current) = 0 then
            return [];
        fi;

        # Inter-layer dedup: prevent exponential parent count blowup.
        # Uses partition normalizer stabilizer for RA (catches swaps of equal
        # factors). With rich invariants (USE_RICH_INTERLAYER_INV), lower the
        # trigger threshold since the dedup is much more effective.
        if i < numLayers and normArg <> fail and Length(current) > 100 then
            current := _InterLayerDedup(current, outerNormForLayer[i],
                                         LargestMovedPoint(P));
        fi;

    od;

    # POST-LIFT GF(2) DEDUP: For elementary abelian P (C_2^d), replace the
    # expensive per-group RepresentativeAction dedup with GF(2) subspace
    # orbit computation under the partition normalizer. This turns O(N^2 * RA)
    # into O(N * |gens|) using integer-packed RREF BFS.
    # The caller's incrementalDedup still handles cross-combo dedup, but
    # within this combo the GF(2) BFS is orders of magnitude faster.
    if IsElementaryAbelian(P) and Size(P) > 1 and normArg <> fail
       and Length(current) > 50 then
        Print("    GF(2) post-lift dedup: ", Length(current), " candidates\n");
        current := _DeduplicateEAFPFbyGF2Orbits(P, current, normArg);
    fi;

    return current;
end;

###############################################################################
# Testing utilities
###############################################################################

# Test on S3 x S3: Should find 11 subdirect products
TestLiftingS3xS3 := function()
    local S3, P, shifted, offs, result, expected;

    Print("Testing lifting on S3 x S3...\n");

    S3 := SymmetricGroup(3);
    shifted := [S3, ShiftGroup(S3, 3)];
    offs := [0, 3];

    if Length(shifted) = 1 then
        P := shifted[1];
    else
        P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    fi;

    Print("  |P| = ", Size(P), "\n");
    Print("  Chief series length: ", Length(ChiefSeries(P)), "\n");

    result := FindFPFClassesByLifting(P, shifted, offs);

    Print("  Found ", Length(result), " FPF subdirect products\n");

    # Count via full enumeration for comparison
    expected := Length(Filtered(
        List(ConjugacyClassesSubgroups(P), Representative),
        S -> IsFPFSubdirect(S, shifted, offs)
    ));

    Print("  Expected (full enum): ", expected, "\n");

    if Length(result) = expected then
        Print("  PASS\n");
        return true;
    else
        Print("  FAIL\n");
        return false;
    fi;
end;

# Test on S4 x S4
TestLiftingS4xS4 := function()
    local S4, P, shifted, offs, result, expected;

    Print("Testing lifting on S4 x S4...\n");

    S4 := SymmetricGroup(4);
    shifted := [S4, ShiftGroup(S4, 4)];
    offs := [0, 4];

    if Length(shifted) = 1 then
        P := shifted[1];
    else
        P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    fi;

    Print("  |P| = ", Size(P), "\n");
    Print("  Chief series length: ", Length(ChiefSeries(P)), "\n");

    result := FindFPFClassesByLifting(P, shifted, offs);

    Print("  Found ", Length(result), " FPF subdirect products\n");

    # Count via full enumeration for comparison
    expected := Length(Filtered(
        List(ConjugacyClassesSubgroups(P), Representative),
        S -> IsFPFSubdirect(S, shifted, offs)
    ));

    Print("  Expected (full enum): ", expected, "\n");

    if Length(result) = expected then
        Print("  PASS\n");
        return true;
    else
        Print("  FAIL\n");
        return false;
    fi;
end;

# Compare lifting vs full enumeration for a partition
CompareLiftingVsFullEnum := function(n, partition)
    local transitiveLists, results_lifting, results_full, IterateCombinations;

    Print("Comparing lifting vs full enum for partition ", partition, " of ", n, "\n");
    Print("================================================================\n");

    transitiveLists := List(partition, d ->
        List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));

    results_lifting := [];
    results_full := [];

    IterateCombinations := function(depth, currentFactors)
        local T, shifted, offs, off, k, P, lifting_result, full_result, allSubs;

        if depth > Length(transitiveLists) then
            shifted := [];
            offs := [];
            off := 0;

            for k in [1..Length(currentFactors)] do
                Add(offs, off);
                Add(shifted, ShiftGroup(currentFactors[k], off));
                off := off + NrMovedPoints(currentFactors[k]);
            od;

            if Length(shifted) = 1 then
                P := shifted[1];
            else
                P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
            fi;

            Print("  Testing factors: ", List(currentFactors, Size), "\n");

            # Lifting method
            lifting_result := FindFPFClassesByLifting(P, shifted, offs);
            Append(results_lifting, lifting_result);

            # Full enumeration
            allSubs := List(ConjugacyClassesSubgroups(P), Representative);
            full_result := Filtered(allSubs, S -> IsFPFSubdirect(S, shifted, offs));
            Append(results_full, full_result);

            Print("    Lifting: ", Length(lifting_result), ", Full: ", Length(full_result), "\n");

            return;
        fi;

        for T in transitiveLists[depth] do
            Add(currentFactors, T);
            IterateCombinations(depth + 1, currentFactors);
            Remove(currentFactors);
        od;
    end;

    IterateCombinations(1, []);

    Print("\nTotal results:\n");
    Print("  Lifting: ", Length(results_lifting), "\n");
    Print("  Full enumeration: ", Length(results_full), "\n");

    return Length(results_lifting) = Length(results_full);
end;

###############################################################################
# Timing Statistics Functions
###############################################################################

# PrintH1TimingStats()
# Print summary of H^1 vs fallback usage and timing
PrintH1TimingStats := function()
    Print("\n========== H^1 Timing Statistics ==========\n");
    Print("H^1 method calls:      ", H1_TIMING_STATS.h1_calls, "\n");
    Print("H^1 total time:        ", H1_TIMING_STATS.h1_time / 1000.0, "s\n");
    Print("Fallback calls:        ", H1_TIMING_STATS.fallback_calls, "\n");
    Print("Coprime skips:         ", H1_TIMING_STATS.coprime_skips, "\n");
    Print("Cache hits:            ", H1_TIMING_STATS.cache_hits, "\n");
    if H1_TIMING_STATS.h1_calls > 0 then
        Print("Avg H^1 time per call: ", (H1_TIMING_STATS.h1_time / H1_TIMING_STATS.h1_calls) / 1000.0, "s\n");
    fi;
    Print("=============================================\n");
end;

# ResetH1TimingStats()
# Reset timing statistics
ResetH1TimingStats := function()
    H1_TIMING_STATS.h1_calls := 0;
    H1_TIMING_STATS.h1_time := 0;
    H1_TIMING_STATS.fallback_calls := 0;
    H1_TIMING_STATS.fallback_time := 0;
    H1_TIMING_STATS.coprime_skips := 0;
    H1_TIMING_STATS.cache_hits := 0;
end;

###############################################################################

Print("Lifting Algorithm loaded.\n");
Print("=========================\n");
Print("Main: FindFPFClassesByLifting(P, shifted_factors, offsets)\n");
Print("Tests: TestLiftingS3xS3(), TestLiftingS4xS4()\n");
Print("Compare: CompareLiftingVsFullEnum(n, partition)\n");
Print("Stats: PrintH1TimingStats(), ResetH1TimingStats()\n\n");
