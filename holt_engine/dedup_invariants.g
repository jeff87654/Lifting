# holt_engine/dedup_invariants.g
#
# Cheap invariants for bucketing before any RepresentativeAction call.
#
# Phase 1 strategy: single source of truth stays in the legacy files
# (lifting_method_fast_v2.g, lifting_algorithm.g). The Holt* wrappers
# here give us a clean API; internals remain byte-identical to the old
# path, preserving optimizations #5 (rich invariants for repeated-part)
# and #6 (cheap invariants for distinct-part) via CURRENT_BLOCK_RANGES
# context. When Phase 4 deletes the old call sites, these wrappers
# become the only path and the old function bodies stay where they are.
#
# Public API:
#   HoltCheapSubgroupInvariant(H)     -> CheapSubgroupInvariantFull(H)
#   HoltExpensiveSubgroupInvariant(H) -> ExpensiveSubgroupInvariant(H)
#   HoltComputeSubgroupInvariant(H)   -> ComputeSubgroupInvariant(H)
#   HoltInvariantKey(inv)             -> InvariantKey(inv)
#   HoltInvariantsMatch(a, b)         -> InvariantsMatch(a, b)

HoltCheapSubgroupInvariant := function(H)
  return CheapSubgroupInvariantFull(H);
end;

HoltExpensiveSubgroupInvariant := function(H)
  return ExpensiveSubgroupInvariant(H);
end;

HoltComputeSubgroupInvariant := function(H)
  return ComputeSubgroupInvariant(H);
end;

HoltInvariantKey := function(inv)
  return InvariantKey(inv);
end;

HoltInvariantsMatch := function(inv1, inv2)
  return InvariantsMatch(inv1, inv2);
end;
