# holt_engine/symmetric_specialization.g
#
# S_n-specific wrapper around the generic engine:
#   - per-partition combo enumeration over transitive-group products
#   - IsFPFSubdirect filter (surjective projection onto each block + FPF)
#   - GF(2) post-lift dedup for elementary-abelian P
#   - Goursat fast path for 2-factor combos
#   - Per-combo partition normalizer (BuildPerComboNormalizer)
#
# Phase 4 strategy: thin wrappers. Single source of truth stays in
# lifting_method_fast_v2.g + lifting_algorithm.g; these wrappers expose
# the S_n-specific helpers through a clean API so Phase 6 (parallel
# runner) can wire run_holt.py against HoltFPFClassesForPartition without
# knowing which underlying function implements it.
#
# Public API:
#   HoltFPFClassesForPartition(n, partition)   -> FindFPFClassesForPartition
#   HoltIsFPFSubdirect(U, shifted, offsets)    -> IsFPFSubdirect
#   HoltBuildPerComboNormalizer(partition, currentFactors, n)
#                                               -> BuildPerComboNormalizer
#   HoltDeduplicateEAFPFbyGF2Orbits(P, fpfList, partNorm)
#                                               -> _DeduplicateEAFPFbyGF2Orbits
#   HoltGoursatFPFSubdirects(T1, T2, pts1, pts2)
#                                               -> GoursatFPFSubdirects

HoltFPFClassesForPartition := function(n, partition)
  return FindFPFClassesForPartition(n, partition);
end;

HoltIsFPFSubdirect := function(U, shifted_factors, offsets)
  return IsFPFSubdirect(U, shifted_factors, offsets);
end;

HoltBuildPerComboNormalizer := function(partition, currentFactors, n)
  return BuildPerComboNormalizer(partition, currentFactors, n);
end;

HoltDeduplicateEAFPFbyGF2Orbits := function(P, fpfList, partNorm)
  return _DeduplicateEAFPFbyGF2Orbits(P, fpfList, partNorm);
end;

HoltGoursatFPFSubdirects := function(T1, T2, pts1, pts2)
  return GoursatFPFSubdirects(T1, T2, pts1, pts2);
end;
