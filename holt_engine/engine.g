# holt_engine/engine.g
#
# Default HOLT_ENGINE_MODE. Must be bound at load time so downstream
# references don't trigger "unbound variable" warnings. See the dispatcher
# comment block (below) for the list of modes.
if not IsBound(HOLT_ENGINE_MODE) then
  HOLT_ENGINE_MODE := "clean_first";
fi;

# Main pipeline per holt_clean_architecture.md §5.
#
#   Input group G
#     -> BuildLiftSeries(G)                       # solvable radical + chief layers
#     -> IdentifyTFTop(G/L); LoadTFClasses        # TF-top subgroup classes
#     -> translate TF classes to subgroups of G containing L
#     -> for each layer from TOP to BOTTOM (M = N_i, N = N_{i-1}):
#          next := []
#          for each parent S (containing M):
#            children := HoltLiftOneParentAcrossLayer(G, layer, S)
#            append children to next
#          dedup children across parents under G-conjugation
#          current := next
#     -> output current
#
# Public API:
#   HoltTopClasses(G, series_rec) -> [ subgroups of G containing L ]
#   HoltSubgroupClassesOfGroup(G) -> [ all subgroup classes of G ]
#   HoltCountConjugacyClasses(n)  -> cached LIFT_CACHE lookup
#
# The existing wrappers (HoltSubgroupClassesOfProduct, _HoltDispatchLift)
# remain as the S_n FPF-filtered path; HoltSubgroupClassesOfGroup is the
# generic Holt pipeline with no FPF filter.

HoltCountConjugacyClasses := function(n)
  local key;
  key := String(n);
  if IsBound(LIFT_CACHE) and IsBound(LIFT_CACHE.(key)) then
    return LIFT_CACHE.(key);
  fi;
  return fail;
end;

# Translate TF-top subgroup class representatives into subgroups of G.
# Each class in G/L corresponds to a subgroup of G containing L (preimage).
HoltTopClasses := function(G, series_rec)
  local L, hom, Q, tf_info, q_classes, X, embedded;
  L := series_rec.radical;
  if Size(L) = Size(G) then
    # G solvable: G/L is trivial; only the trivial subgroup of G/L,
    # whose preimage is L = G itself.
    return [G];
  fi;

  # When L is trivial, G = G/L as a set but NaturalHomomorphismByNormalSubgroup
  # wraps Q in a different representation that breaks PreImages downstream.
  # Bypass the hom and look up classes directly against G.
  if Size(L) = 1 then
    tf_info := HoltIdentifyTFTop(G);
    tf_info.canonical_group := G;
    return HoltLoadTFClasses(tf_info);
  fi;

  hom := NaturalHomomorphismByNormalSubgroup(G, L);
  Q := ImagesSource(hom);
  tf_info := HoltIdentifyTFTop(Q);
  tf_info.canonical_group := Q;
  q_classes := HoltLoadTFClasses(tf_info);

  embedded := [];
  for X in q_classes do
    Add(embedded, PreImages(hom, X));
  od;
  return embedded;
end;

# Cache-only variant: returns fail if nothing is cached. Used by
# HoltFPFSubgroupClassesOfProduct to consult the warm cache before
# deciding between direct CCS and max-subgroup-tree BFS. When the warm
# cache has an entry (even for |Q| > HOLT_TF_CCS_DIRECT), using it is
# strictly cheaper than running max-rec from scratch.
HoltTopClassesIfCached := function(G, series_rec)
  local L, hom, Q, tf_info, q_classes, X, embedded;
  L := series_rec.radical;
  if Size(L) = Size(G) then
    return [G];
  fi;
  if Size(L) = 1 then
    tf_info := HoltIdentifyTFTop(G);
    tf_info.canonical_group := G;
    q_classes := HoltLoadTFClassesIfCached(tf_info);
    if q_classes = fail then return fail; fi;
    return q_classes;
  fi;
  hom := NaturalHomomorphismByNormalSubgroup(G, L);
  Q := ImagesSource(hom);
  tf_info := HoltIdentifyTFTop(Q);
  tf_info.canonical_group := Q;
  q_classes := HoltLoadTFClassesIfCached(tf_info);
  if q_classes = fail then return fail; fi;
  embedded := [];
  for X in q_classes do
    Add(embedded, PreImages(hom, X));
  od;
  return embedded;
end;

# Dedup a list of subgroups under G-conjugation.
#
# Implementation: invariant bucketing. Groups that land in different
# buckets cannot be conjugate, so we only pay RepresentativeAction inside
# each bucket. Uses HoltCheapSubgroupInvariant (order + orbit-partition +
# cycle-type histogram + orders of small-index characteristic subgroups).
#
# Legacy CheapSubgroupInvariantFull assumes the FPF context and references
# CURRENT_BLOCK_RANGES -- for generic G we pass a conservative bucketing
# key (order + orbit sizes + abelian invariants + exponent).

_HoltGenericInvariantKey := function(H)
  local moved, orbits, sizes;
  moved := MovedPoints(H);
  if Length(moved) = 0 then
    orbits := [];
  else
    orbits := Orbits(H, moved);
  fi;
  sizes := SortedList(List(orbits, Length));
  return [
    Size(H),
    sizes,
    SortedList(AbelianInvariants(H)),
    Exponent(H),
    IsAbelian(H),
    Size(DerivedSubgroup(H))
  ];
end;

# Matrix-orbit dedup for elementary-abelian ambient G.
# Subgroups of (Z/p)^d correspond to F_p subspaces; G's normalizer acts
# linearly, so `OrbitsDomain(mat_group, subspaces, OnSubspacesByCanonicalBasis)`
# replaces O(N^2) RepresentativeAction with O(|orbit| * |gens| * d^2)
# matrix operations. Works for arbitrary prime p and arbitrary d.
#
# Returns subgroup representatives of G-orbits.
_HoltOrbitDedupEA := function(subgroups, G, normalizer)
  local p, d, pcgs, field, actMats, gen, mat, i, img, exps, allBases,
        H, H_basis, basesByDim, matGroup, dim, orbits, reps,
        vecToSubgroup, repSubgroup;
  if Length(subgroups) <= 1 then return subgroups; fi;

  p := PrimePGroup(G);
  pcgs := Pcgs(G);
  d := Length(pcgs);
  field := GF(p);
  if d = 0 then return [TrivialSubgroup(G)]; fi;

  # Normalizer's action on G = (Z/p)^d as d x d matrices over F_p
  actMats := [];
  for gen in GeneratorsOfGroup(normalizer) do
    mat := NullMat(d, d, field);
    for i in [1..d] do
      img := pcgs[i] ^ gen;
      if not img in G then
        return fail;  # normalizer doesn't preserve G; caller handles
      fi;
      exps := ExponentsOfPcElement(pcgs, img);
      mat[i] := List(exps, x -> x * One(field));
    od;
    Add(actMats, mat);
  od;
  if Length(actMats) = 0 then
    Add(actMats, IdentityMat(d, field));
  fi;

  # Represent each candidate subgroup as its F_p-basis in G (RREF)
  basesByDim := List([0..d], i -> []);
  for H in subgroups do
    if Size(H) = 1 then
      Add(basesByDim[1], rec(subgroup := H, basis := []));
    elif Size(H) = Size(G) then
      Add(basesByDim[d+1], rec(subgroup := H,
                                basis := IdentityMat(d, field)));
    else
      H_basis := List(GeneratorsOfGroup(H),
        e -> List(ExponentsOfPcElement(pcgs, e), x -> x * One(field)));
      H_basis := SemiEchelonMat(H_basis).vectors;
      Add(basesByDim[Length(H_basis)+1],
          rec(subgroup := H, basis := H_basis));
    fi;
  od;

  matGroup := Group(actMats);
  reps := [];
  # Trivial (dim 0) and full (dim d) are always orbit singletons
  if Length(basesByDim[1]) > 0 then
    Add(reps, basesByDim[1][1].subgroup);
  fi;
  if d > 0 and Length(basesByDim[d+1]) > 0 then
    Add(reps, basesByDim[d+1][1].subgroup);
  fi;
  # Proper subspace dims: orbit computation
  for dim in [1..d-1] do
    if Length(basesByDim[dim+1]) = 0 then continue; fi;
    if Length(basesByDim[dim+1]) = 1 then
      Add(reps, basesByDim[dim+1][1].subgroup);
      continue;
    fi;
    orbits := OrbitsDomain(matGroup,
                            List(basesByDim[dim+1], x -> x.basis),
                            OnSubspacesByCanonicalBasis);
    # One representative per orbit. The first element of each orbit
    # IS an element of our input list (OrbitsDomain starts each orbit
    # from an element of the given domain), so we can match by identity.
    for i in [1..Length(orbits)] do
      H_basis := orbits[i][1];
      for img in [1..Length(basesByDim[dim+1])] do
        if basesByDim[dim+1][img].basis = H_basis then
          Add(reps, basesByDim[dim+1][img].subgroup);
          break;
        fi;
      od;
    od;
  od;
  return reps;
end;

# M7 threshold: above this bucket size, refine further with the expensive
# (ConjugacyClasses / 2-subset orbit) invariant before falling to exact
# dedup. This must be fairly high: on S17 [5,4,4,4] real reps, cheap buckets
# of size 20-104 were already small enough for indexed UF, while the rich
# invariant spent most of its time in ConjugacyClasses and 2-subset orbits.
if not IsBound(_HOLT_RICH_BUCKET_THRESHOLD) then
  _HOLT_RICH_BUCKET_THRESHOLD := 200;
fi;

# GAP rec field names are capped at 1023 chars. Invariant-based keys for
# subgroup bucketing can exceed this (especially `String(ExpensiveSubgroup-
# Invariant(H))` on large H). Reduce every key to a short hex hash — collisions
# only mean two distinct invariants share a bucket, where pairwise RA then
# correctly separates them. Zero correctness risk.
_HoltShortHashOf := function(s)
  local h, c, i;
  h := 0;
  for i in [1..Length(s)] do
    c := IntChar(s[i]);
    h := (h * 131 + c) mod 1000000007;
  od;
  return HexStringInt(h);
end;

if not IsBound(_HOLT_RA_COUNT) then _HOLT_RA_COUNT := 0; fi;

_HoltDedupBucketByRA := function(bucket, G)
  local reps, H, K, found;
  reps := [];
  for H in bucket do
    found := false;
    for K in reps do
      _HOLT_RA_COUNT := _HOLT_RA_COUNT + 1;
      if RepresentativeAction(G, H, K, OnPoints) <> fail then
        found := true;
        break;
      fi;
    od;
    if not found then
      Add(reps, H);
    fi;
  od;
  return reps;
end;

# Exact subgroup key for indexed orbit dedup.
#
# This is deliberately based on the full element set, not on generators:
# two equal subgroups can arrive with different generating sets.  The hash is
# only an index key; callers still verify subgroup equality before unioning.
if not IsBound(HOLT_UF_INDEX_BUCKET_MIN) then HOLT_UF_INDEX_BUCKET_MIN := 40; fi;
if not IsBound(HOLT_UF_INDEX_MAX_GROUP_ORDER) then
  HOLT_UF_INDEX_MAX_GROUP_ORDER := 20000;
fi;
if not IsBound(HOLT_ENABLE_UF_INDEX) then HOLT_ENABLE_UF_INDEX := true; fi;

_HoltSubgroupElementHash := function(H)
  local strs;
  strs := List(Elements(H), String);
  Sort(strs);
  return _HoltShortHashOf(Concatenation(strs));
end;

# M8: Canonical-image bucket dedup.
#
# For each subgroup H in the bucket, enumerate its G-orbit via BFS from the
# generator graph (O(|orbit| · |gens G|) conjugations). Canonicalize by
# taking the lexicographically-smallest `SortedString(gens of orbit element)`.
# Two subgroups with the same canonical key are G-conjugate — one
# `RepresentativeAction` call is replaced by one BFS.
#
# Win is proportional to bucket size and orbit cost:
#   - O(k^2) RA backtracks (pre-M8) → O(k · orbit_BFS) canonicalizations.
#   - Each orbit_BFS is bounded by HOLT_CANON_ORBIT_CAP; above that we fall
#     back to pairwise RA for the whole bucket.
#
# Stable key choice (`_HoltSortedGenKey`): sorted list of String(generator).
# A group is uniquely identified by its generating set. Different paths to
# the same group produce different specific gen sequences → different keys,
# but the BFS's smallest-key over the full orbit is still canonical (since
# the orbit is the same SET of groups regardless of traversal order).
if not IsBound(HOLT_CANON_ORBIT_CAP) then HOLT_CANON_ORBIT_CAP := 300; fi;
# Default off: benchmarks showed M8 orbit-BFS per-subgroup cost exceeds its
# RA savings on most partitions ([4,4,4,2] was 2.25x slower than baseline).
# M6+M7+M9 already reduce RA count to ~1-2% of pairs (see profile data); the
# canonical-form BFS adds more work than it avoids. Code kept for future
# benchmarking on pathological FPF buckets; flip HOLT_DISABLE_CANON_DEDUP
# := false to opt in.
if not IsBound(HOLT_CANON_BUCKET_MIN) then HOLT_CANON_BUCKET_MIN := 4; fi;
if not IsBound(HOLT_DISABLE_CANON_DEDUP) then HOLT_DISABLE_CANON_DEDUP := true; fi;

_HoltSortedGenKey := function(H)
  local strs;
  strs := List(GeneratorsOfGroup(H), String);
  Sort(strs);
  return _HoltShortHashOf(Concatenation(strs));
end;

# Smallest key over the full G-orbit of H. Returns fail if the orbit
# exceeds HOLT_CANON_ORBIT_CAP (caller falls back to pairwise RA).
_HoltCanonicalOrbitKey := function(H, G)
  local queue, keys, i, H_cur, g, H_g, key_g, gens_g;
  queue := [H];
  keys := rec();
  keys.(_HoltSortedGenKey(H)) := true;
  i := 1;
  while i <= Length(queue) do
    H_cur := queue[i];
    for g in GeneratorsOfGroup(G) do
      gens_g := List(GeneratorsOfGroup(H_cur), x -> x^g);
      H_g := Group(gens_g);
      key_g := _HoltSortedGenKey(H_g);
      if not IsBound(keys.(key_g)) then
        keys.(key_g) := true;
        Add(queue, H_g);
        if Length(queue) > HOLT_CANON_ORBIT_CAP then
          return fail;
        fi;
      fi;
    od;
    i := i + 1;
  od;
  # Smallest key across the orbit.
  return Minimum(RecNames(keys));
end;

_HoltDedupBucketByCanonical := function(bucket, G)
  local canonical_buckets, H, canon, allReps, key;
  if Length(bucket) <= 1 then return bucket; fi;
  canonical_buckets := rec();
  for H in bucket do
    canon := _HoltCanonicalOrbitKey(H, G);
    if canon = fail then
      return fail;  # signal caller to fall back to RA
    fi;
    if not IsBound(canonical_buckets.(canon)) then
      canonical_buckets.(canon) := [];
    fi;
    Add(canonical_buckets.(canon), H);
  od;
  # Canonical key is a 32-bit polynomial hash, so ~0.03% collision rate per
  # pair; construction-path dependence of gen strings also lets genuine
  # G-conjugates canonicalize differently. Use canonical as a prefilter
  # only: within each canonical sub-bucket, verify with pairwise RA.
  # Collisions downgrade M8 from "definitive" to "bucketing finer than M7"
  # — still strictly faster than raw RA because each sub-bucket is tiny.
  allReps := [];
  for key in RecNames(canonical_buckets) do
    Append(allReps, _HoltDedupBucketByRA(canonical_buckets.(key), G));
  od;
  return allReps;
end;

# M9: Union-Find orbit dedup.
#
# Instead of O(k^2) pairwise RepresentativeAction(G, H_i, H_j), iterate
# generators of G: for each H_i and each gen g, compute H_i^g and search
# the bucket for an existing H_j equal as a group. Union(i, j) merges
# their classes. After processing, each union-find root is one class rep.
#
# Cost: O(k * |gens G| * k) group-equality tests (linear scan) + O(k) unions.
# Each group equality is O(|gens H|) membership tests in a stab chain —
# generally much cheaper than an RA backtrack over G.
#
# Falls back to canonical / RA if the bucket is tiny (overhead not worth it).
_HoltUnionFindFind := function(parent, i)
  local root, j, next;
  root := i;
  while parent[root] <> root do root := parent[root]; od;
  # Path compression
  j := i;
  while parent[j] <> root do
    next := parent[j]; parent[j] := root; j := next;
  od;
  return root;
end;

_HoltDedupBucketByUnionFind := function(bucket, G)
  local n, parent, i, j, H_g, gens_g, g, H, gens_G, ri, rj, reps,
        size_bucket_i, useIndex, maxSize, keyToIdx, key, idxs;
  n := Length(bucket);
  if n <= 1 then return bucket; fi;
  gens_G := GeneratorsOfGroup(G);
  if Length(gens_G) = 0 then return bucket; fi;
  parent := List([1..n], i -> i);
  # Precompute sizes to quick-skip mismatches in equality checks.
  size_bucket_i := List(bucket, Size);
  maxSize := Maximum(size_bucket_i);

  # For large buckets, replace the O(k) linear scan for each generator image
  # by an exact element-set index.  We still verify H_g = bucket[j], so hash
  # collisions cannot merge distinct subgroups.
  useIndex := HOLT_ENABLE_UF_INDEX
              and n >= HOLT_UF_INDEX_BUCKET_MIN
              and maxSize <= HOLT_UF_INDEX_MAX_GROUP_ORDER;
  keyToIdx := rec();
  if useIndex then
    for i in [1..n] do
      key := _HoltSubgroupElementHash(bucket[i]);
      if not IsBound(keyToIdx.(key)) then
        keyToIdx.(key) := [];
      fi;
      Add(keyToIdx.(key), i);
    od;
  fi;

  for i in [1..n] do
    ri := _HoltUnionFindFind(parent, i);
    for g in gens_G do
      gens_g := List(GeneratorsOfGroup(bucket[i]), x -> x^g);
      H_g := Group(gens_g);
      if useIndex then
        key := _HoltSubgroupElementHash(H_g);
        if IsBound(keyToIdx.(key)) then
          idxs := keyToIdx.(key);
          for j in idxs do
            if j <> i
               and size_bucket_i[j] = size_bucket_i[i]
               and _HoltUnionFindFind(parent, j) <> ri
               and H_g = bucket[j] then
              rj := _HoltUnionFindFind(parent, j);
              parent[ri] := rj;
              ri := rj;
              break;
            fi;
          od;
        fi;
      else
        for j in [1..n] do
          if j <> i
             and size_bucket_i[j] = size_bucket_i[i]
             and _HoltUnionFindFind(parent, j) <> ri
             and H_g = bucket[j] then
            rj := _HoltUnionFindFind(parent, j);
            parent[ri] := rj;
            ri := rj;
            break;
          fi;
        od;
      fi;
    od;
  od;
  reps := [];
  for i in [1..n] do
    if _HoltUnionFindFind(parent, i) = i then
      Add(reps, bucket[i]);
    fi;
  od;
  return reps;
end;

HoltDedupUnderG := function(subgroups, G)
  local buckets, H, keyStr, allReps, useRich, subBuckets, subKey, bucket,
        ea_reps, ra_start, t_start, last_log, n_in, bucketKeys, numBuckets,
        bucketSizes, bucketIdx, bucketCount, total_buckets, now, emitProgress;
  if Length(subgroups) <= 1 then return subgroups; fi;
  n_in := Length(subgroups);

  # Kill switch: when set, return the input unchanged and let the caller
  # (legacy incrementalDedup) do all dedup. On S_18 partitions like [10,4,4]
  # the ExpensiveSubgroupInvariant bucketing cost ~48 min to collapse 1040
  # to 632, while GAP's RepresentativeAction in legacy did the same in ~2 min.
  # Useful when the dedup set is large and RA-cheap.
  if IsBound(HOLT_DISABLE_DEDUP) and HOLT_DISABLE_DEDUP then
    return subgroups;
  fi;

  # Fast path: if G is elementary abelian, use matrix-orbit dedup
  # directly on all subgroups at once (arbitrary prime p, any dim).
  if IsPGroup(G) and IsElementaryAbelian(G) then
    ea_reps := _HoltOrbitDedupEA(subgroups, G, G);  # use G as its own normalizer
    if ea_reps <> fail then
      return ea_reps;
    fi;
  fi;

  # Rich invariant bucket: if we're inside an FPF partition context
  # (CURRENT_BLOCK_RANGES set by FindFPFClassesForPartition), use the
  # partition-aware CheapSubgroupInvariantFull via HoltCheapSubgroupInvariant.
  # Its per-block orbit lengths + TransitiveIdentification dramatically
  # reduce bucket sizes for repeated-part partitions. Fall back to the
  # coarser generic key for generic HoltSubgroupClassesOfGroup runs.
  useRich := IsBound(CURRENT_BLOCK_RANGES)
             and Length(CURRENT_BLOCK_RANGES) > 0
             and IsBound(HoltCheapSubgroupInvariant)
             and not (IsBound(HOLT_DISABLE_RICH_DEDUP) and HOLT_DISABLE_RICH_DEDUP);

  buckets := rec();
  for H in subgroups do
    if useRich then
      keyStr := _HoltShortHashOf(String(HoltCheapSubgroupInvariant(H)));
    else
      keyStr := _HoltShortHashOf(String(_HoltGenericInvariantKey(H)));
    fi;
    if not IsBound(buckets.(keyStr)) then
      buckets.(keyStr) := [];
    fi;
    Add(buckets.(keyStr), H);
  od;

  # Progress header: log once at start of large dedup passes.
  ra_start := _HOLT_RA_COUNT;
  t_start := Runtime();
  last_log := t_start;
  bucketKeys := RecNames(buckets);
  numBuckets := Length(bucketKeys);
  bucketSizes := List(bucketKeys, k -> Length(buckets.(k)));
  if n_in >= 200 then
    Print("    [HoltDedup] ", n_in, " classes, ", numBuckets, " buckets ",
          "(max ", Maximum(bucketSizes), ", median ",
          bucketSizes[Int((Length(bucketSizes)+1)/2)],
          ", useRich=", useRich, ")\n");
  fi;

  allReps := [];
  bucketCount := 0;
  for keyStr in bucketKeys do
    bucket := buckets.(keyStr);
    bucketCount := bucketCount + 1;
    # M7: for large buckets, split further by the richer (expensive)
    # invariant before pairwise RA. On dense partitions this collapses
    # thousands of O(k^2) RA calls into a linear-time invariant pass.
    if Length(bucket) > _HOLT_RICH_BUCKET_THRESHOLD
       and IsBound(ExpensiveSubgroupInvariant) then
      subBuckets := rec();
      for H in bucket do
        subKey := _HoltShortHashOf(String(ExpensiveSubgroupInvariant(H)));
        if not IsBound(subBuckets.(subKey)) then
          subBuckets.(subKey) := [];
        fi;
        Add(subBuckets.(subKey), H);
      od;
      for subKey in RecNames(subBuckets) do
        Append(allReps, _HoltDedupSubBucket(subBuckets.(subKey), G));
      od;
    else
      Append(allReps, _HoltDedupSubBucket(bucket, G));
    fi;

    # Emit a progress line every ~60s on large dedup runs.
    now := Runtime();
    emitProgress := n_in >= 200 and (now - last_log) >= 60000;
    if emitProgress then
      Print("    [HoltDedup] bucket ", bucketCount, "/", numBuckets,
            ", reps=", Length(allReps), ", RA=", _HOLT_RA_COUNT - ra_start,
            " (+", Int((now - t_start)/1000), "s)\n");
      last_log := now;
    fi;
  od;

  if n_in >= 200 then
    Print("    [HoltDedup] done: ", n_in, " -> ", Length(allReps),
          " reps, RA=", _HOLT_RA_COUNT - ra_start,
          ", ", Int((Runtime() - t_start)/1000), "s\n");
  fi;
  return allReps;
end;

# Dispatch inside a bucket, in order of preference:
#   (1) M8 canonical-orbit-key when bucket is medium-sized and the orbit
#       enumeration fits in HOLT_CANON_ORBIT_CAP.
#   (2) M9 Union-Find over generator-conjugation when M8 bails on orbit cap.
#   (3) Pairwise RepresentativeAction fallback.
if not IsBound(HOLT_UF_BUCKET_MIN) then HOLT_UF_BUCKET_MIN := 6; fi;
_HoltDedupSubBucket := function(bucket, G)
  local result;
  # M8: canonical orbit key.
  if Length(bucket) >= HOLT_CANON_BUCKET_MIN
     and not (IsBound(HOLT_DISABLE_CANON_DEDUP) and HOLT_DISABLE_CANON_DEDUP) then
    result := _HoltDedupBucketByCanonical(bucket, G);
    if result <> fail then return result; fi;
  fi;
  # M9: Union-Find orbit dedup.
  if Length(bucket) >= HOLT_UF_BUCKET_MIN
     and not (IsBound(HOLT_DISABLE_UF_DEDUP) and HOLT_DISABLE_UF_DEDUP) then
    return _HoltDedupBucketByUnionFind(bucket, G);
  fi;
  # Fallback: pairwise RA.
  return _HoltDedupBucketByRA(bucket, G);
end;

# Dedup under an extension G = B . W by first deduping under the normal base
# subgroup B, then applying the quotient generators to the B-orbit reps.
# In the symmetric-product FPF case, B is the product of per-block normalizers
# and W is generated by same-type block swaps.  If the input is not stable
# under the quotient action, this returns fail so callers can use the ordinary
# full-G dedup path.
if not IsBound(HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP) then
  HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;
fi;
if not IsBound(HOLT_BLOCK_QUOTIENT_MAX_INPUT) then
  HOLT_BLOCK_QUOTIENT_MAX_INPUT := 500;
fi;

HoltDedupUnderNormalQuotient := function(subgroups, G, B)
  local baseReps, qGens, parent, n, keyBuckets, useRich, H, key, i, g,
        img, idxs, j, found, ri, rj, reps;

  if Length(subgroups) <= 1 then return subgroups; fi;
  if Length(subgroups) > HOLT_BLOCK_QUOTIENT_MAX_INPUT then
    return fail;
  fi;
  if B = fail or Size(B) = Size(G) then
    return HoltDedupUnderG(subgroups, G);
  fi;
  if not IsSubgroup(G, B) then
    return fail;
  fi;
  if not IsNormal(G, B) then
    return fail;
  fi;

  baseReps := HoltDedupUnderG(subgroups, B);
  if Length(baseReps) <= 1 then return baseReps; fi;

  qGens := Filtered(GeneratorsOfGroup(G), g -> not g in B);
  if Length(qGens) = 0 then return baseReps; fi;

  useRich := IsBound(CURRENT_BLOCK_RANGES)
             and Length(CURRENT_BLOCK_RANGES) > 0
             and IsBound(HoltCheapSubgroupInvariant)
             and not (IsBound(HOLT_DISABLE_RICH_DEDUP) and HOLT_DISABLE_RICH_DEDUP);

  keyBuckets := rec();
  for i in [1..Length(baseReps)] do
    if useRich then
      key := _HoltShortHashOf(String(HoltCheapSubgroupInvariant(baseReps[i])));
    else
      key := _HoltShortHashOf(String(_HoltGenericInvariantKey(baseReps[i])));
    fi;
    if not IsBound(keyBuckets.(key)) then
      keyBuckets.(key) := [];
    fi;
    Add(keyBuckets.(key), i);
  od;

  n := Length(baseReps);
  parent := List([1..n], i -> i);
  for i in [1..n] do
    ri := _HoltUnionFindFind(parent, i);
    for g in qGens do
      img := Group(List(GeneratorsOfGroup(baseReps[i]), x -> x^g));
      if useRich then
        key := _HoltShortHashOf(String(HoltCheapSubgroupInvariant(img)));
      else
        key := _HoltShortHashOf(String(_HoltGenericInvariantKey(img)));
      fi;
      if not IsBound(keyBuckets.(key)) then
        return fail;
      fi;
      idxs := keyBuckets.(key);
      found := false;
      for j in idxs do
        if _HoltUnionFindFind(parent, j) <> ri
           and Size(baseReps[j]) = Size(img) then
          _HOLT_RA_COUNT := _HOLT_RA_COUNT + 1;
          if RepresentativeAction(B, img, baseReps[j], OnPoints) <> fail then
            rj := _HoltUnionFindFind(parent, j);
            parent[ri] := rj;
            ri := rj;
            found := true;
            break;
          fi;
        elif _HoltUnionFindFind(parent, j) = ri
             and Size(baseReps[j]) = Size(img) then
          _HOLT_RA_COUNT := _HOLT_RA_COUNT + 1;
          if RepresentativeAction(B, img, baseReps[j], OnPoints) <> fail then
            found := true;
            break;
          fi;
        fi;
      od;
      if not found then
        return fail;
      fi;
    od;
  od;

  reps := [];
  for i in [1..n] do
    if _HoltUnionFindFind(parent, i) = i then
      Add(reps, baseReps[i]);
    fi;
  od;
  return reps;
end;

# Full clean pipeline: enumerate all subgroup classes of G.
HoltSubgroupClassesOfGroup := function(G)
  local series_rec, layers_topdown, current, layer, next_classes, parent, children;

  series_rec := HoltBuildLiftSeries(G);

  # Start from classes of G containing L (pulled back from G/L via TF db).
  current := HoltTopClasses(G, series_rec);

  # Process layers top-down: the highest-index layer (closest to L) first.
  # series_rec.layers is bottom-up ordered (layers[1] near trivial,
  # layers[r] near L). Reverse so the first layer we process has M = L.
  layers_topdown := Reversed(series_rec.layers);

  for layer in layers_topdown do
    next_classes := [];
    for parent in current do
      children := HoltLiftOneParentAcrossLayer(G, layer, parent);
      Append(next_classes, children);
    od;
    # Dedup across parents: two parents S1, S2 may produce G-conjugate children.
    current := HoltDedupUnderG(next_classes, G);
  od;

  return current;
end;

# FPF-aware clean pipeline, filtered post-enumeration. Suitable as a
# correctness oracle at small degrees — at large degrees use the
# per-layer variant HoltFPFSubgroupClassesOfProduct below.
HoltCleanFPFSubgroupClasses := function(P, shifted_factors, offsets)
  local all_classes;
  all_classes := HoltSubgroupClassesOfGroup(P);
  return Filtered(all_classes,
    H -> IsFPFSubdirect(H, shifted_factors, offsets));
end;

# Block-factored partition normalizer: the product of per-block
# N_{S_{d_k}}(T_k) plus block-swap generators for same-(degree, TI) blocks.
# Built directly from already-shifted factors + offsets (no unshift needed
# at the call site). Used by HoltFPFSubgroupClassesOfProduct for intermediate
# per-layer dedup — dramatically smaller than S_n-scale Npart, so pairwise
# RepresentativeAction inside invariant buckets is orders of magnitude cheaper.
#
# For TransitiveIdentification we unshift locally (conjugate to [1..d])
# since TI expects a transitive action on [1..d].
_HoltBlockBaseNormalizer := function(shifted_factors, offsets, n)
  local gens, numFactors, partition, k, d, startPt, endPt, Tk, normTk;

  numFactors := Length(shifted_factors);

  partition := [];
  for k in [1..numFactors] do
    if k < numFactors then
      Add(partition, offsets[k+1] - offsets[k]);
    else
      Add(partition, n - offsets[k]);
    fi;
  od;

  gens := [];
  for k in [1..numFactors] do
    d := partition[k];
    startPt := offsets[k] + 1;
    endPt := offsets[k] + d;
    Tk := shifted_factors[k];
    normTk := Normalizer(SymmetricGroup([startPt..endPt]), Tk);
    Append(gens, GeneratorsOfGroup(normTk));
  od;

  if Length(gens) = 0 then return Group(()); fi;
  return Group(gens);
end;

_HoltBlockFactoredNormalizer := function(shifted_factors, offsets, n)
  local gens, numFactors, partition, k, d,
        groupsByDegTI, unshiftPerm, unshifted, keyStr, positions,
        m, p, q, offset_p, offset_q, mapping, i, perm;

  numFactors := Length(shifted_factors);

  partition := [];
  for k in [1..numFactors] do
    if k < numFactors then
      Add(partition, offsets[k+1] - offsets[k]);
    else
      Add(partition, n - offsets[k]);
    fi;
  od;

  gens := ShallowCopy(GeneratorsOfGroup(
      _HoltBlockBaseNormalizer(shifted_factors, offsets, n)));

  groupsByDegTI := rec();
  for k in [1..numFactors] do
    d := partition[k];
    if offsets[k] > 0 then
      unshiftPerm := MappingPermListList(
          [offsets[k]+1..offsets[k]+d], [1..d]);
      unshifted := Group(List(GeneratorsOfGroup(shifted_factors[k]),
                              g -> g^unshiftPerm));
    else
      unshifted := shifted_factors[k];
    fi;
    keyStr := Concatenation(String(d), "_",
              String(TransitiveIdentification(unshifted)));
    if not IsBound(groupsByDegTI.(keyStr)) then
      groupsByDegTI.(keyStr) := [];
    fi;
    Add(groupsByDegTI.(keyStr), k);
  od;

  for keyStr in RecNames(groupsByDegTI) do
    positions := groupsByDegTI.(keyStr);
    if Length(positions) >= 2 then
      d := partition[positions[1]];
      for m in [1..Length(positions)-1] do
        p := positions[m];
        q := positions[m+1];
        offset_p := offsets[p];
        offset_q := offsets[q];
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

  if Length(gens) = 0 then return Group(()); fi;
  return Group(gens);
end;

# FPF filter pushed INTO the lift.
#
# Key invariant: if a subgroup T fails IsFPFSubdirect (either loses
# FPF-action or loses surjective projection on some block), then every
# descendant T' <= T also fails:
#   - FPF-action: a non-identity element of T with a fixed point is still
#     in T' if it happens to live there. More strongly, T' having an
#     element fixing a point inherits from T.
#   - FPF-surjective: p_i(T') <= p_i(T) ≠ T_i, so not surjective.
# Therefore filtering by IsFPFSubdirect at every layer boundary prunes
# entire subtrees without losing any valid FPF class.
HoltFPFSubgroupClassesOfProduct := function(arg)
  local P, shifted_factors, offsets, partNormalizer, normArg, blockNorm,
        blockBaseNorm, blockNormOK, n_points,
        series_rec, layers_topdown, current, layer, next_classes,
        parent, children, saved_factors, saved_offsets, dedupGroup,
        baseDedupGroup, quotientDedup,
        _layerIdx, _numLayers, _parentIdx, _numParents, _t0, _writeHb;

  P := arg[1];
  shifted_factors := arg[2];
  offsets := arg[3];

  # 4th arg optional: partition normalizer N (where P <= N <= S_n). When
  # provided, dedup uses N instead of P — gives stronger per-partition
  # equivalence matching the legacy outer-loop normalizer dedup.
  if Length(arg) >= 4 and arg[4] <> fail then
    partNormalizer := arg[4];
  else
    partNormalizer := P;
  fi;
  normArg := partNormalizer;

  # 5th arg optional: block-factored normalizer B (product of per-block
  # N_{S_{d_k}}(T_k) + same-type block swaps, see _HoltBlockFactoredNormalizer).
  # When provided, intermediate per-layer dedup runs under Normalizer(B, M_i)
  # rather than Normalizer(normArg, M_i). For combos where normArg = S_n
  # this reduces the dedup ambient group from ~n! down to ~(d_1)! · (d_2)! · …
  # — orders of magnitude smaller — so pairwise RA inside buckets is
  # dramatically cheaper. If not supplied, we compute it locally. Safety
  # gate: we only use blockNorm for intermediate dedup when blockNorm ⊆
  # normArg (so dedup never over-merges; final normArg-dedup catches any
  # cross-block equivalences missed).
  n_points := LargestMovedPoint(P);
  blockNorm := fail;
  blockBaseNorm := fail;
  if Length(arg) >= 5 and arg[5] <> fail then
    blockNorm := arg[5];
  elif Size(normArg) > Size(P) then
    blockBaseNorm := _HoltBlockBaseNormalizer(
        shifted_factors, offsets, n_points);
    blockNorm := _HoltBlockFactoredNormalizer(
        shifted_factors, offsets, n_points);
  fi;
  blockNormOK := false;
  if blockNorm <> fail
     and Size(blockNorm) < Size(normArg)
     and IsSubgroup(normArg, blockNorm)
     and not (IsBound(HOLT_DISABLE_BLOCKNORM) and HOLT_DISABLE_BLOCKNORM) then
    blockNormOK := true;
  fi;

  # Expose FPF context to _HoltLiftFixedIntersection's impossibility pruner.
  # Save/restore so a nested call (e.g. recursion into a helper that also
  # invokes the lift) doesn't leak stale factors.
  saved_factors := _HOLT_LIFT_FACTORS;
  saved_offsets := _HOLT_LIFT_OFFSETS;
  _HOLT_LIFT_FACTORS := shifted_factors;
  _HOLT_LIFT_OFFSETS := offsets;

  # Product-specific chief series: CoprimePriorityChiefSeries gives better
  # layer ordering for FPF subdirects (coprime factors grouped, factor
  # structure respected). Only safe when the P's chief factors are all
  # prime-power (solvable P) — HoltExtractLayers errors on non-abelian
  # simple chief factors. Fall back to radical+TF-top split otherwise.
  if IsSolvableGroup(P) and Length(shifted_factors) >= 1 then
    series_rec := HoltBuildLiftSeriesFromProduct(P, shifted_factors);
  else
    series_rec := HoltBuildLiftSeries(P);
  fi;

  # Stage A: top classes, FPF-filtered immediately.
  #
  # Cache-first: try HoltTopClassesIfCached regardless of |Q|. If the warm
  # cache (or any in-memory / TF_SUBGROUP_LATTICE / TransitiveGroup tier)
  # has an entry for this (key, sig), use it — strictly cheaper than
  # running max-rec or CCS from scratch, since the cost of computing Q's
  # subgroup lattice is amortized across every combo sharing this TF top.
  #
  # On cache miss, decide between:
  #  - HoltTopSubgroupsByMaximals when |P/Pt| > HOLT_TF_CCS_DIRECT (max-rec
  #    BFS with FPF projection pruning; cheaper for large Q but not cached)
  #  - HoltTopClasses otherwise (triggers CCS compute + cache write-through)
  current := HoltTopClassesIfCached(P, series_rec);
  if current = fail then
    if series_rec.radical <> fail
       and IsBound(HOLT_TF_CCS_DIRECT)
       and Size(P) / Size(series_rec.radical) > HOLT_TF_CCS_DIRECT then
      current := HoltTopSubgroupsByMaximals(
          P, series_rec.radical, shifted_factors, partNormalizer);
    else
      current := HoltTopClasses(P, series_rec);
    fi;
  fi;
  current := Filtered(current,
    H -> IsFPFSubdirect(H, shifted_factors, offsets));

  # Stage B: layer lifting with per-layer FPF filter.
  # HoltLiftOneParentAcrossLayer accepts an optional 4th arg `parent_norm`;
  # we pass fail so it falls back to Normalizer(P, S).
  #
  # Dedup strategy (correctness): at layer i (with upper term M_i), the
  # intermediate dedup uses N_{normArg}(M_i) — the normalizer-stabilizer
  # of M_i inside normArg. This is wider than P (P itself normalizes
  # every chief-series member), and narrower than normArg (elements that
  # don't fix M_i can swap series members and break lift equivalence).
  # Using N_{normArg}(M_i) avoids the two-class merge bug observed on
  # S_14 [8,3,3] combo [T(3,2),T(3,2),T(8,22)] (clean found 27 instead
  # of 29 under unconditional normArg-dedup).
  # Final layer uses normArg (full Npart) for canonical Npart-class reps.
  layers_topdown := Reversed(series_rec.layers);
  _numLayers := Length(layers_topdown);
  _t0 := Runtime();

  # Heartbeat helper for the clean pipeline. Writes a progress line to
  # _HEARTBEAT_FILE if bound. Called between parents and between layers.
  _writeHb := function(msg)
    if IsBound(_HEARTBEAT_FILE) and _HEARTBEAT_FILE <> "" then
      PrintTo(_HEARTBEAT_FILE, "alive ",
              Int((Runtime() - _t0) / 1000), "s clean ", msg, "\n");
    fi;
  end;

  _layerIdx := 0;
  for layer in layers_topdown do
    _layerIdx := _layerIdx + 1;
    _numParents := Length(current);
    _writeHb(Concatenation("layer ", String(_layerIdx), "/",
              String(_numLayers), " |M/N|=", String(layer.p^layer.d),
              " parents=", String(_numParents)));
    next_classes := [];
    _parentIdx := 0;
    for parent in current do
      _parentIdx := _parentIdx + 1;
      # Heartbeat every 10 parents OR every 30s of layer time on big layers.
      if _numParents >= 5 and (_parentIdx mod 10 = 0
         or _parentIdx = _numParents) then
        _writeHb(Concatenation("layer ", String(_layerIdx), "/",
                  String(_numLayers), " parent ", String(_parentIdx), "/",
                  String(_numParents), " children=",
                  String(Length(next_classes))));
      fi;
      children := HoltLiftOneParentAcrossLayer(P, layer, parent, fail);
      children := Filtered(children,
        T -> IsFPFSubdirect(T, shifted_factors, offsets));
      Append(next_classes, children);
    od;
    _writeHb(Concatenation("layer ", String(_layerIdx), "/",
              String(_numLayers), " dedup ",
              String(Length(next_classes)), " -> ?"));
    # Layer-stabilizer normalizer (safe intermediate dedup group).
    # M := layer.M is G-normal; Normalizer(normArg, M) ⊇ P and ⊆ normArg.
    # M6: prefer blockNorm (block-factored) over normArg (Npart = S_n-scale)
    # when available and verified as subgroup. Final normArg-dedup below
    # catches any cross-block equivalences this step misses.
    if blockNormOK then
      dedupGroup := Normalizer(blockNorm, layer.M);
      if blockBaseNorm <> fail
         and HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP then
        baseDedupGroup := Normalizer(blockBaseNorm, layer.M);
        quotientDedup := HoltDedupUnderNormalQuotient(
            next_classes, dedupGroup, baseDedupGroup);
        if quotientDedup <> fail then
          current := quotientDedup;
        else
          current := HoltDedupUnderG(next_classes, dedupGroup);
        fi;
      else
        current := HoltDedupUnderG(next_classes, dedupGroup);
      fi;
    else
      dedupGroup := Normalizer(normArg, layer.M);
      current := HoltDedupUnderG(next_classes, dedupGroup);
    fi;
    _writeHb(Concatenation("layer ", String(_layerIdx), "/",
              String(_numLayers), " dedup -> ",
              String(Length(current)), " done"));
  od;

  # Final dedup under Npart to get canonical Npart-class reps.
  if Size(normArg) > Size(P) and Length(current) > 1 then
    if blockNormOK and blockBaseNorm <> fail
       and HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP then
      quotientDedup := HoltDedupUnderNormalQuotient(
          current, blockNorm, blockBaseNorm);
      if quotientDedup <> fail then
        current := quotientDedup;
      else
        current := HoltDedupUnderG(current, normArg);
      fi;
    else
      current := HoltDedupUnderG(current, normArg);
    fi;
  fi;

  # Restore previous FPF context (see saved_factors above).
  _HOLT_LIFT_FACTORS := saved_factors;
  _HOLT_LIFT_OFFSETS := saved_offsets;

  return current;
end;

# Legacy S_n FPF-filtered path (Phase 4 thin wrapper - preserved).
HoltSubgroupClassesOfProduct := function(arg)
  return CallFuncList(FindFPFClassesByLifting, arg);
end;

# Does X (a subgroup of Q = P/Pt) have X * F = Q for every factor image F?
# Equivalently, does X project onto every factor quotient H_i*Pt/Pt?
# For BFS pruning in HoltTopSubgroupsByMaximals — if X fails surjectivity
# on any factor, no descendant of X can either.
# FPF projection filter: does X project onto T_i for each factor i?
#
# Algebraic equivalence: π_i(X) = T_i  iff  <X, coFactor_i> = Q,
# where coFactor_i := <F_j : j ≠ i>  is the group generated by all the
# OTHER factors. Intuition: X * (all-other-factors) covers Q iff X
# supplies everything factor i contributes, i.e. X projects onto T_i.
#
# Historical note: earlier code tested `X * F_i = Q` (X together with the
# i-th factor generates Q). That's correct for 2 factors (F_1 and F_2 are
# mutual complements in Q) but WRONG for 3+ factors — it overprunes and
# rejects genuine FPF subdirects (e.g. the diagonal A_5 in A_5^3). Each
# caller must therefore pass `coFactorsInQ`, not just `factorImagesInQ`.
_HoltXCoversAllFactorImages := function(X, coFactorsInQ, Q)
  local cf;
  for cf in coFactorsInQ do
    if Size(ClosureGroup(X, cf)) <> Size(Q) then
      return false;
    fi;
  od;
  return true;
end;

# FPF-aware max-subgroup BFS in Q = P/Pt.
#
# User-specified algorithm: starting from Q, descend through maximal
# subgroups; at each node check that X * F_i = Q for every factor image F_i
# (equivalently, X projects onto every factor quotient); skip subtrees
# whose projection already fails; dedup under Npart/Pt.
#
# Output: representatives of Npart-classes of subgroups S with Pt <= S <= P
# such that S/Pt projects onto every factor image in Q. These are precisely
# the TF-top components eligible to be lifted through the radical layers
# into FPF subdirects of P.
#
# Used by the dispatcher for oversized TF tops where direct CCS is infeasible
# (|Q| > HOLT_TF_CCS_DIRECT).
#
# Args:
#   P        ambient direct product
#   Pt       solvable radical of P (pass RadicalGroup(P) or equivalent)
#   factors  shifted_factors (list of groups, one per orbit block)
#   Npart    partition normalizer
HoltTopSubgroupsByMaximals := function(P, Pt, factors, Npart)
  local homP, Q, factorImagesQ, coFactorsInQ, coFactorGens, j, seen_buckets,
        queue, output_Q, X, maxes, Y, invKey, alreadySeen, K, U,
        preimages, S, S_found, i;

  # Work in Q = P/Pt for the BFS (cheaper), then lift candidates to P
  # and dedup there under Npart-conjugacy. This avoids having to project
  # Npart (which usually isn't a subgroup of P) down to Q.
  if Size(Pt) = 1 then
    Q := P;
    homP := IdentityMapping(P);
    factorImagesQ := factors;
  else
    homP := NaturalHomomorphismByNormalSubgroup(P, Pt);
    Q := ImagesSource(homP);
    factorImagesQ := List(factors, H -> Image(homP, H));
  fi;

  # Precompute coFactor_i = <F_j : j ≠ i> for each i. Used by the FPF
  # projection filter (π_i(X) = T_i  iff  <X, coFactor_i> = Q).
  coFactorsInQ := [];
  for i in [1..Length(factorImagesQ)] do
    coFactorGens := [];
    for j in [1..Length(factorImagesQ)] do
      if j <> i then
        Append(coFactorGens, GeneratorsOfGroup(factorImagesQ[j]));
      fi;
    od;
    if Length(coFactorGens) = 0 then
      Add(coFactorsInQ, TrivialSubgroup(Q));
    else
      Add(coFactorsInQ, Subgroup(Q, coFactorGens));
    fi;
  od;

  queue := [Q];
  seen_buckets := rec();
  output_Q := [];

  while Length(queue) > 0 do
    X := Remove(queue);

    # Prune: X must project onto every factor image in Q. If it fails even
    # one, no descendant (which is smaller) can recover surjectivity.
    if not _HoltXCoversAllFactorImages(X, coFactorsInQ, Q) then
      continue;
    fi;

    # Dedup under Q-conjugacy (cheap, happens in Q). Final Npart-dedup
    # happens post-lift on subgroups of P. This inner Q-dedup is a cheap
    # optimization to reduce the number of preimages we materialize.
    invKey := String(_HoltGenericInvariantKey(X));
    alreadySeen := false;
    if IsBound(seen_buckets.(invKey)) then
      for K in seen_buckets.(invKey) do
        if Size(K) = Size(X) then
          _HOLT_RA_COUNT := _HOLT_RA_COUNT + 1;
          if RepresentativeAction(Q, K, X) <> fail then
            alreadySeen := true;
            break;
          fi;
        fi;
      od;
    else
      seen_buckets.(invKey) := [];
    fi;
    if alreadySeen then continue; fi;
    Add(seen_buckets.(invKey), X);
    Add(output_Q, X);

    # Expand via maximal subgroup classes of X. Each maximal is a
    # candidate parent class for FPF lifting, subject to the projection
    # filter on the next visit.
    maxes := List(ConjugacyClassesMaximalSubgroups(X), Representative);
    for Y in maxes do
      if _HoltXCoversAllFactorImages(Y, coFactorsInQ, Q) then
        Add(queue, Y);
      fi;
    od;
  od;

  # Lift back: preimages in P.
  if Size(Pt) = 1 then
    preimages := output_Q;
  else
    preimages := List(output_Q, U -> PreImages(homP, U));
  fi;

  # Final dedup under Npart-conjugacy in P. Q-conjugacy is a weaker
  # equivalence than Npart-conjugacy (Q ⊆ Npart/Pt as conjugating groups
  # in general), so this may collapse further.
  output_Q := [];  # reuse as output list in P
  for S in preimages do
    S_found := false;
    for K in output_Q do
      if Size(K) = Size(S) then
        _HOLT_RA_COUNT := _HOLT_RA_COUNT + 1;
        if RepresentativeAction(Npart, S, K) <> fail then
          S_found := true;
          break;
        fi;
      fi;
    od;
    if not S_found then
      Add(output_Q, S);
    fi;
  od;
  return output_Q;
end;

# FPF-filtered max-recursion path: enumerate all subgroup classes of P
# via HoltSubgroupsViaMaximals, then filter for FPF-subdirectness.
# This is Holt's "pure recursive" path — bypasses the layer-lifting
# structure entirely and relies on the maximal-subgroup database.
HoltFPFViaMaximals := function(P, shifted_factors, offsets)
  local all_subs;
  all_subs := HoltSubgroupsViaMaximals(P);
  return Filtered(all_subs,
    H -> IsFPFSubdirect(H, shifted_factors, offsets));
end;

# Cheap pre-check: estimate TF-top size. Used to decide between the
# layer-lifting clean pipeline (good for solvable-heavy P) and the pure
# maximal-subgroup path (good for large nonsolvable TF tops).
_HoltEstimateTFSize := function(P)
  local L;
  L := RadicalGroup(P);
  return Size(P) / Size(L);
end;

# Fast-path detector. Returns true if legacy FindFPFClassesByLifting will
# hit one of its one-shot fast paths:
#   1. small abelian P (|P| <= 256)
#   2. small non-abelian P (|P| <= 48)
#   3. 2-factor non-abelian (Goursat's lemma)
#   4. 3+ factor with 3+ D_4 (= TG(4,3)) factors
#
# When any of these applies, we route directly to FindFPFClassesByLifting
# because (a) its fast paths are already highly tuned, and (b) running the
# clean pipeline on these cases is pure overhead. The clean pipeline is
# reserved for the "general" case — which is where its architecture wins.
_HoltIsLegacyFastPathCase := function(P, shifted_factors)
  local f, n_d4;
  if IsAbelian(P) and Size(P) <= 256 then
    return true;
  fi;
  if not IsAbelian(P) and Size(P) <= 48 then
    return true;
  fi;
  if Length(shifted_factors) = 2 and not IsAbelian(P) then
    return true;
  fi;
  if Length(shifted_factors) >= 3 then
    # S_n>=5 fast-path removed 2026-04-23: benchmark on S_17 [5,5,5,2]
    # combo [T(2,1),T(5,5),T(5,5),T(5,5)] showed legacy took 5346s on the
    # final A_5 layer (ComplementClassesRepresentatives fails on non-solvable
    # M/N, falls back to NonSolvableComplementClassReps), while Holt clean
    # with HoltTopSubgroupsByMaximals finished in 17s with identical output.
    n_d4 := Number(shifted_factors, f ->
      NrMovedPoints(f) = 4 and TransitiveIdentification(f) = 3);
    if n_d4 >= 3 and IsBound(D4_CUBE_CACHE) then
      return true;
    fi;
  fi;
  return false;
end;

# Mode-based dispatcher. HOLT_ENGINE_MODE controls routing:
#   "legacy"        - always call FindFPFClassesByLifting (battle-tested)
#   "clean_first"   - fast-path-detect -> legacy; else clean pipeline
#                     -> legacy fallback on error
#   "clean"         - always try clean pipeline, legacy fallback on error
#   "max_rec"       - try HoltFPFViaMaximals, legacy fallback on error
#
# Default is "clean_first" per the performance plan (plans/i-m-having-a-lot-
# mighty-deer.md). Legacy still owns the five FAST PATHS (small-abelian,
# small-CCS, Goursat-2, S_n, D_4^3); the clean pipeline owns the general
# layer-lifting case where Holt architecture pays off.
_HoltDispatchLift := function(arg)
  local P, shifted, result;
  if not IsBound(HOLT_ENGINE_MODE) then
    HOLT_ENGINE_MODE := "clean_first";
  fi;

  if HOLT_ENGINE_MODE = "legacy" then
    return CallFuncList(FindFPFClassesByLifting, arg);
  fi;

  P := arg[1];
  shifted := arg[2];

  # "clean_first" routes fast-path cases straight to legacy. This preserves
  # the 5x Goursat / D_4^3 / S_n speedups intact.
  if HOLT_ENGINE_MODE = "clean_first"
     and _HoltIsLegacyFastPathCase(P, shifted) then
    return CallFuncList(FindFPFClassesByLifting, arg);
  fi;

  if HOLT_ENGINE_MODE = "clean" or HOLT_ENGINE_MODE = "clean_first" then
    BreakOnError := false;
    result := CALL_WITH_CATCH(
      function() return CallFuncList(HoltFPFSubgroupClassesOfProduct, arg); end,
      []);
    BreakOnError := true;
    if result[1] = true then return result[2]; fi;
  fi;

  if HOLT_ENGINE_MODE = "max_rec" then
    BreakOnError := false;
    result := CALL_WITH_CATCH(
      function()
        return CallFuncList(HoltFPFViaMaximals, arg{[1..3]});
      end,
      []);
    BreakOnError := true;
    if result[1] = true then return result[2]; fi;
  fi;

  # Fallback to legacy on any error
  return CallFuncList(FindFPFClassesByLifting, arg);
end;
