# holt_engine/orbit_action.g
#
# All orbit computations used for deduplication flow through here:
#   - orbits on H^1 cocycle classes under the outer normalizer action
#
# Phase 2 strategy: thin wrappers around the legacy implementations in
# h1_action.g. The affine translation piece (fix #28) and the
# non-solvable usePcgs=false -> fail guard live in the underlying
# ComputeOuterActionOnH1; these wrappers expose them through a clean API.
#
# Public API:
#   HoltComputeH1Action(cohomRec, module, n, S, L, homSL, P)
#       -> ComputeOuterActionOnH1 (affine, with non-solvable fail guard)
#   HoltBuildH1ActionRecord(cohomRec, module, outerNormGens, S, L, homSL, P)
#       -> BuildH1ActionRecordFromOuterNorm
#   HoltOrbitRepsOnCocycles(Q, M_bar, outerNormGens, S, L, homSL, P [,fpfFilter])
#       -> GetH1OrbitRepresentatives (same variable-arg signature)

HoltComputeH1Action := function(cohomRecord, module, n, S, L, homSL, P)
  return ComputeOuterActionOnH1(cohomRecord, module, n, S, L, homSL, P);
end;

HoltBuildH1ActionRecord := function(cohomRecord, module, outerNormGens, S, L, homSL, P)
  return BuildH1ActionRecordFromOuterNorm(cohomRecord, module, outerNormGens, S, L, homSL, P);
end;

HoltOrbitRepsOnCocycles := function(arg)
  return CallFuncList(GetH1OrbitRepresentatives, arg);
end;
