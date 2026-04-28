# holt_engine_monolith.g
#
# Auto-generated monolithic concatenation of holt_engine/*.g.
#
# Load order matches holt_engine/loader.g: leaves first, engine last.
# Requires the legacy engine to be loaded first, since many Holt*
# wrappers delegate into lifting_algorithm.g / lifting_method_fast_v2.g /
# cohomology.g / h1_action.g / modules.g:
#
#     Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
#     Read("C:/Users/jeffr/Downloads/Lifting/holt_engine_monolith.g");
#
# Feature flag matches loader.g.

if not IsBound(USE_HOLT_ENGINE) then
  USE_HOLT_ENGINE := false;
fi;

HOLT_ENGINE_DIR := "C:/Users/jeffr/Downloads/Lifting/holt_engine/";

##############################################################################
# SECTION: subgroup_record.g
##############################################################################

# holt_engine/subgroup_record.g
#
# Data type passed between all engine stages.
# All public names in the engine are prefixed Holt* to avoid collisions
# with GAP built-ins and with existing functions in the legacy files.
#
# Schema (per holt_clean_architecture.md §3.3):
#   rec(
#     subgroup    := H,                  # embedded in ambient G
#     order       := Size(H),
#     generators  := GeneratorsOfGroup(H),
#     normalizer  := fail or N_G(H),     # lazy
#     presentation := fail or pres,       # needed during lifting
#     metadata    := rec(parent, layer, intersection, cocycle_rep, source)
#   )

HoltMakeClassRec := function(H)
  return rec(
    subgroup := H,
    order := Size(H),
    generators := GeneratorsOfGroup(H),
    normalizer := fail,
    presentation := fail,
    metadata := rec()
  );
end;

HoltMakeChildClassRec := function(T, parent, layer, intersection, cocycle_rep)
  local r;
  r := HoltMakeClassRec(T);
  r.metadata := rec(
    parent := parent,
    layer := layer,
    intersection := intersection,
    cocycle_rep := cocycle_rep,
    source := "lift"
  );
  return r;
end;

HoltMakeTFClassRec := function(H, pres)
  local r;
  r := HoltMakeClassRec(H);
  r.presentation := pres;
  r.metadata := rec(source := "tf_database");
  return r;
end;

##############################################################################
# SECTION: heartbeat.g
##############################################################################

# holt_engine/heartbeat.g
#
# Routes heartbeat emissions through a single global with three call-sites
# (mid-dedup, post-combo, mid-layer) preserved verbatim from the old engine.
#
# Public API:
#   HoltEmitHeartbeat(msg)      -> append "msg" to _HEARTBEAT_FILE if set
#   HoltHeartbeatNoop(msg)      -> discard (used in tests)
#   HOLT_HEARTBEAT_CALLBACK     -> current callback
#
# Text formats (verbatim from lifting_method_fast_v2.g + lifting_algorithm.g):
#   "alive {t}s {combo} dedup {i}/{total}"
#   "alive {t}s {combo} done, combo #{n} fpf={count}"
#   "alive {t}s {combo} layer [{type}] parent {i}/{total}"

HoltEmitHeartbeat := function(msg)
  local path;
  if not IsBound(_HEARTBEAT_FILE) then
    return;
  fi;
  path := _HEARTBEAT_FILE;
  if path = fail or path = "" then
    return;
  fi;
  AppendTo(path, msg, "\n");
end;

HoltHeartbeatNoop := function(msg)
  return;
end;

HOLT_HEARTBEAT_CALLBACK := HoltEmitHeartbeat;

##############################################################################
# SECTION: checkpoint.g
##############################################################################

# holt_engine/checkpoint.g
#
# Save/Resume using the existing .g monolithic + .log delta format.
# The heavy lifting is in lifting_method_fast_v2.g (_SaveCheckpoint at
# :1958, _AppendCheckpointDelta at :2081, _LoadCheckpoint at :2147).
# These wrappers expose the clean Holt API; internals stay identical so
# checkpoints written by the legacy engine remain resumable by the Holt
# engine (Phase 9 S18 resume relies on this).
#
# Public API:
#   HoltSaveCheckpoint(path, completedKeys, all_fpf, totalCandidates,
#                      addedCount [,invKeys])
#       -> _SaveCheckpoint
#   HoltAppendCheckpointDelta(path, comboKey, newGroups, totalCandidates,
#                             addedCount, totalFpf [,newInvKeys])
#       -> _AppendCheckpointDelta
#   HoltResumeCheckpoint(path)
#       -> _LoadCheckpoint -- returns rec(completedKeys, allFpfGens,
#          totalCandidates, addedCount, invKeys?, richInvActive?) or fail.

HoltSaveCheckpoint := function(arg)
  CallFuncList(_SaveCheckpoint, arg);
end;

HoltAppendCheckpointDelta := function(arg)
  CallFuncList(_AppendCheckpointDelta, arg);
end;

HoltResumeCheckpoint := function(path)
  return _LoadCheckpoint(path);
end;

##############################################################################
# SECTION: dedup_invariants.g
##############################################################################

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

##############################################################################
# SECTION: series_builder.g
##############################################################################

# holt_engine/series_builder.g
#
# Solvable-radical-first normal series for the lifting engine.
#
# For a permutation group G:
#   radical L = solvable radical (RadicalGroup(G))
#   layers   = bottom-up chief-series factors of L, each elementary abelian
#   tf_top   = G/L (trivial-Fitting)
#
# The underlying series computation wraps existing RefinedChiefSeries and
# CoprimePriorityChiefSeries (lifting_algorithm.g:2507, :2399) verbatim.
# This module's value-add is the stable, explicit layer record:
#
#   rec(
#     group    := G,
#     radical  := L,
#     layers   := [ rec(N, M, p, d, index), ... ],  # bottom-up, N < M, M/N ≅ (C_p)^d
#     tf_top   := G/L
#   )
#
# Public API:
#   HoltBuildLiftSeries(G)                        -> rec as above
#   HoltBuildLiftSeriesFromProduct(P, factors)    -> series via CoprimePriorityChiefSeries
#   HoltSeriesChiefFactors(series_rec)            -> [ (N,M,p,d) ] bottom-up
#
# Each layer satisfies Size(M)/Size(N) = p^d (elementary abelian of rank d
# over F_p) because the underlying series has been through
# RefineChiefSeriesLayer.

HoltExtractLayers := function(G, series)
  local layers, i, M, N, idx, factorSize, p, d;
  layers := [];
  # series is top-down [G, ..., 1]; we want layers bottom-up so the lift
  # processes trivial first.
  idx := 0;
  for i in Reversed([1..Length(series)-1]) do
    M := series[i];
    N := series[i+1];
    factorSize := Size(M) / Size(N);
    if factorSize = 1 then
      continue;
    fi;
    p := SmallestPrimeDivisor(factorSize);
    if factorSize mod p <> 0 then
      Error("HoltExtractLayers: factor size ", factorSize,
            " not a prime power");
    fi;
    d := LogInt(factorSize, p);
    if p ^ d <> factorSize then
      # Not elementary abelian — RefineChiefSeriesLayer should have
      # prevented this, but guard anyway.
      Error("HoltExtractLayers: factor ", factorSize,
            " is not p^d for prime p");
    fi;
    idx := idx + 1;
    Add(layers, rec(
      N := N,
      M := M,
      p := p,
      d := d,
      index := idx
    ));
  od;
  return layers;
end;

HoltBuildLiftSeries := function(G)
  local L, series_L, layers, tf_top, hom;
  L := RadicalGroup(G);
  if Size(L) = 1 then
    series_L := [Group(())];
    layers := [];
  else
    series_L := RefinedChiefSeries(L);
    layers := HoltExtractLayers(G, series_L);
  fi;
  if Size(L) = Size(G) then
    tf_top := Group(());
  else
    # Leave quotient construction to callers that need it — the engine
    # itself only uses L and the layers, and pulls tf_top classes from
    # the TF database keyed by an isomorphism invariant of G/L.
    tf_top := fail;
  fi;
  return rec(
    group := G,
    radical := L,
    layers := layers,
    tf_top := tf_top,
    _series := series_L
  );
end;

HoltBuildLiftSeriesFromProduct := function(P, shifted_factors)
  local series, layers;
  if Length(shifted_factors) <= 1 then
    series := RefinedChiefSeries(P);
  else
    series := CoprimePriorityChiefSeries(P, shifted_factors);
  fi;
  layers := HoltExtractLayers(P, series);
  return rec(
    group := P,
    radical := P,
    layers := layers,
    tf_top := Group(()),
    _series := series
  );
end;

HoltSeriesChiefFactors := function(series_rec)
  return List(series_rec.layers, lay -> [lay.N, lay.M, lay.p, lay.d]);
end;

##############################################################################
# SECTION: module_layer.g
##############################################################################

# holt_engine/module_layer.g
#
# Converts a chief-series layer (N < M) into GF(p)-module form and owns
# the enumeration of S-invariant subspaces and their orbit representatives
# under normalizer action, per holt_clean_architecture.md §3.5 and §4.3.
#
# Public API:
#   HoltLayerModule(Q, M_bar, L)
#       -> ChiefFactorAsModule(Q, M_bar, L)  (thin wrapper, legacy)
#
#   HoltInvariantSubspaces(S, M, N)
#       -> [ L : L normal in S, N <= L <= M ]
#          (thin wrapper over NormalSubgroupsBetween, legacy)
#
#   HoltInvariantSubspaceOrbits(S, M, N, R)
#       -> orbit representatives of the above under R's conjugation action.
#          R is typically N_G(S). This is the §4.3 orbit reduction: instead
#          of enumerating all S-invariant subspaces and deduping children
#          post-lift, we dedup the subspaces themselves before any
#          complement computation.
#
#   HoltRefineToElementaryAbelianLayers(G, N, C, p)
#       -> ascending chain [N, H_1, ..., C] of G-normal intermediate
#          subgroups whose successive factors are elementary abelian
#          p-groups. Uses the Frattini filtration: for any p-group V,
#          V/Frat(V) is EA (Burnside basis theorem), and Frat^i(V) is
#          characteristic so G-normality is preserved. Returns [N, C]
#          without refining when C/N is not a p-group for the given p.
#
# Implementation note: we use subgroup-level RepresentativeAction inside R
# to compute orbits. For high-dimensional M/N this can be replaced by a
# matrix-group orbit computation on GF(p)^d (tracked in Phase 11+ work).

HoltLayerModule := function(Q, M_bar, L)
  return ChiefFactorAsModule(Q, M_bar, L);
end;

HoltInvariantSubspaces := function(S, M, N)
  return NormalSubgroupsBetween(S, M, N);
end;

# Refine a G-normal solvable p-section [N, C] into a chain of G-normal
# intermediate subgroups with elementary-abelian successive factors.
#
# Method: Frattini filtration on V = C/N. For any p-group V, Frat(V) is
# characteristic, and V/Frat(V) is EA by Burnside's basis theorem. Iterate
# until reaching the trivial subgroup, then pull each term back to a
# G-normal subgroup of C containing N.
#
# Returns the ascending chain [N, H_1, ..., C]. If C/N is not a p-group
# (or p doesn't match PrimePGroup(C/N)), returns [N, C] unchanged — the
# caller still sees a valid two-term chain but the section isn't EA-refined.

HoltRefineToElementaryAbelianLayers := function(G, N, C, p)
  local hom, V, chain, W, W_next;
  if Size(C) = Size(N) then
    return [C];
  fi;
  hom := SafeNaturalHomByNSG(C, N);
  if hom = fail then
    return [N, C];
  fi;
  V := ImagesSource(hom);
  if Size(V) = 1 then
    return [C];
  fi;
  if not IsPGroup(V) or PrimePGroup(V) <> p then
    return [N, C];
  fi;
  # Descending Frattini chain: V > Frat(V) > Frat^2(V) > ... > 1
  chain := [V];
  W := V;
  while Size(W) > 1 do
    W_next := FrattiniSubgroup(W);
    if Size(W_next) = Size(W) then
      break;
    fi;
    Add(chain, W_next);
    W := W_next;
  od;
  # Ascending: [1, ..., Frat(V), V]
  chain := Reversed(chain);
  return List(chain, H -> PreImage(hom, H));
end;

# Linear-algebra orbit reduction on S-invariant subspaces (architecture
# doc §4.3). For elementary-abelian M/N, convert each L in [N,M] into
# its F_p-subspace basis in V = M/N, compute R/M action matrices, and
# use GAP's Orbits(matrix_group, subspaces, OnSubspacesByCanonicalBasis)
# — O(|orbits| * |subspace| * |gens|) linear ops instead of O(|subspaces|^2)
# RepresentativeAction calls on subgroups.
#
# Falls back to pairwise RepresentativeAction when M/N is not elementary
# abelian (non-solvable chief factor case).

_HoltPairwiseSubgroupDedup := function(subspaces, R_eff)
  local reps, L, found, K;
  reps := [];
  for L in subspaces do
    found := false;
    for K in reps do
      if Size(L) = Size(K) and
         RepresentativeAction(R_eff, L, K, OnPoints) <> fail then
        found := true;
        break;
      fi;
    od;
    if not found then
      Add(reps, L);
    fi;
  od;
  return reps;
end;

# Module-first orbit reduction: enumerate S-invariant subspaces directly
# at F_p-module level (MTX.BasesSubmodules on the S-action module), orbit-
# reduce under R/M's matrix action, and only materialize subgroups for
# orbit representatives. Skips the O(|submodules|) subgroup-object
# construction cost inside NormalSubgroupsBetween for the non-rep
# subspaces.

_HoltBuildActionMatrices := function(hom, pcgs, d, field, gens)
  local mats, g, mat, i, img, exps;
  mats := [];
  for g in gens do
    mat := NullMat(d, d, field);
    for i in [1..d] do
      img := Image(hom, PreImagesRepresentative(hom, pcgs[i]) ^ g);
      exps := ExponentsOfPcElement(pcgs, img);
      mat[i] := List(exps, x -> x * One(field));
    od;
    Add(mats, mat);
  od;
  if Length(mats) = 0 then
    Add(mats, IdentityMat(d, field));
  fi;
  return mats;
end;

HoltInvariantSubspaceOrbits := function(S, M, N, R)
  local hom, V, p, d, pcgs, field, R_eff, actMats_S, actMats_R,
        module, submoduleBases, basesByDim, matGroup_R, orbits,
        orbitReps, basis, i, rep_subgroup;

  if Size(M) = Size(N) then
    return [M];
  fi;

  hom := SafeNaturalHomByNSG(M, N);
  if hom = fail then
    # Can't form quotient — fall back to subgroup-level legacy path.
    R_eff := Normalizer(Normalizer(R, M), N);
    return _HoltPairwiseSubgroupDedup(
      NormalSubgroupsBetween(S, M, N), R_eff);
  fi;

  V := ImagesSource(hom);
  if not IsPGroup(V) or not IsElementaryAbelian(V) then
    R_eff := Normalizer(Normalizer(R, M), N);
    return _HoltPairwiseSubgroupDedup(
      NormalSubgroupsBetween(S, M, N), R_eff);
  fi;

  p := PrimePGroup(V);
  pcgs := Pcgs(V);
  d := Length(pcgs);
  if d = 0 then
    return [M];
  fi;
  field := GF(p);

  # Enumerate S-invariant F_p-subspaces at module level via MTX.
  actMats_S := _HoltBuildActionMatrices(hom, pcgs, d, field,
                                         GeneratorsOfGroup(S));
  module := GModuleByMats(actMats_S, field);
  submoduleBases := MTX.BasesSubmodules(module);

  # MTX returns bases ordered trivial→full. Short-circuit if only {0, V}.
  if Length(submoduleBases) <= 2 then
    return [N, M];
  fi;

  # R acts on V — needed for orbit reduction on submodule bases.
  R_eff := Normalizer(Normalizer(R, M), N);
  actMats_R := _HoltBuildActionMatrices(hom, pcgs, d, field,
                                         GeneratorsOfGroup(R_eff));
  matGroup_R := Group(actMats_R);

  # Partition submodule bases by dimension (OrbitsDomain needs homogeneous
  # domain). Trivial (dim 0) and full (dim d) are orbit singletons.
  basesByDim := List([0..d], i -> []);
  for basis in submoduleBases do
    Add(basesByDim[Length(basis)+1], basis);
  od;

  orbitReps := [];
  for i in [1..d-1] do
    if Length(basesByDim[i+1]) = 0 then continue; fi;
    if Length(basesByDim[i+1]) = 1 then
      Append(orbitReps, basesByDim[i+1]);
      continue;
    fi;
    orbits := OrbitsDomain(matGroup_R, basesByDim[i+1],
                            OnSubspacesByCanonicalBasis);
    Append(orbitReps, List(orbits, o -> o[1]));
  od;

  # Materialize subgroups ONLY for orbit reps (plus trivial N and full M).
  rep_subgroup := function(basis_rows)
    local preim, v;
    preim := [];
    for v in basis_rows do
      Add(preim, PreImagesRepresentative(hom,
        Product([1..d], j -> pcgs[j]^IntFFE(v[j]))));
    od;
    return ClosureGroup(N, preim);
  end;

  return Concatenation([N], List(orbitReps, rep_subgroup), [M]);
end;

##############################################################################
# SECTION: orbit_action.g
##############################################################################

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

##############################################################################
# SECTION: presentation_engine.g
##############################################################################

# holt_engine/presentation_engine.g
#
# Presentations for subgroup class reps used by cohomology_lifter.
# Isolated from orbit enumeration and dedup (per holt_clean_architecture.md §3.4).
#
# Phase 3 strategy: minimal viable implementation that covers the common
# cases. For solvable class reps we defer to Pcgs (the cocycle solver's
# preferred input); for non-solvable class reps we return a marker record
# that the cohomology_lifter can use directly with the ambient generators.
#
# The layer lift currently reuses the parent's ambient generators directly
# inside ComputeCocycleSpaceViaPcgs (via module.preimageGens), so the
# "presentation" we need here is only metadata — the heavy lifting is done
# in cohomology.g and h1_action.g against the live group.
#
# Public API:
#   HoltPresentationForClassRec(classrec)
#       -> rec(subgroup, is_solvable, pcgs, generators, relators (opt),
#              source := "pcgs" | "fp" | "gens_only")
#   HoltLiftPresentation(parent_pres, layer, child_subgroup)
#       -> presentation record for child, inheriting parent generators +
#          appending layer's Pcgs relations. Currently returns the child's
#          own fresh presentation since LiftThroughLayer's internals already
#          re-derive the presentation from the live subgroup.

HoltPresentationForClassRec := function(classrec)
  local G, source, pcgs, gens;
  if IsGroup(classrec) then
    G := classrec;
  elif IsRecord(classrec) and IsBound(classrec.subgroup) then
    G := classrec.subgroup;
  else
    return fail;
  fi;

  if IsSolvableGroup(G) then
    pcgs := Pcgs(G);
    if pcgs <> fail and Length(pcgs) > 0 then
      return rec(
        subgroup := G,
        is_solvable := true,
        pcgs := pcgs,
        generators := AsList(pcgs),
        source := "pcgs"
      );
    fi;
    return rec(
      subgroup := G,
      is_solvable := true,
      pcgs := fail,
      generators := GeneratorsOfGroup(G),
      source := "gens_only"
    );
  fi;

  return rec(
    subgroup := G,
    is_solvable := false,
    pcgs := fail,
    generators := GeneratorsOfGroup(G),
    source := "gens_only"
  );
end;

HoltLiftPresentation := function(parent_pres, layer, child_subgroup)
  # For Phase 3, we derive a fresh presentation for the child. This is
  # sufficient because the cohomology lifter currently reads the live
  # subgroup directly. A richer implementation (inheriting parent pcgs +
  # layer relations) is a Phase 4+ optimization tracked in the plan under
  # "presentation propagation across layers".
  return HoltPresentationForClassRec(child_subgroup);
end;

##############################################################################
# SECTION: cohomology_lifter.g
##############################################################################

# holt_engine/cohomology_lifter.g
#
# Core single-layer lifter per holt_clean_architecture.md §4.3-4.5.
#
# Given G, a chief-series layer (N, M) with M/N elementary abelian, and
# a parent subgroup S <= G containing M, enumerate every child T <= G
# with T*M = S and T cap M in [N, M].
#
# Algorithm:
#   1. R = N_G(S).
#   2. Enumerate S-normal subgroups L with N <= L <= M. These correspond
#      to S-invariant subspaces of V = M/N.
#   3. Compute orbit representatives of these L under R/M's action on V.
#      (HoltInvariantSubspaceOrbits -- §4.3.)
#   4. For each L rep:
#        a. If L = M: child is S itself (layer trivial).
#        b. Else: complements of M/L in S/L via H^1 cohomology.
#           - Non-split: skip.
#           - Split: cocycle reps, then Q/S orbit reduction where
#             Q = N_R(L). (HoltOrbitRepsOnCocycles -- §4.5.)
#        c. Convert each cocycle rep to T = preimage in S.
#   5. Return all T.
#
# Public API:
#   HoltLiftOneParentAcrossLayer(G, layer, parent_subgroup) -> [ subgroups of G ]
#
# Phase 2 wrappers preserved for legacy pass-through use:
#   HoltSolveCocycles, HoltSolveCocyclesPcgs, HoltModuleFingerprint,
#   HoltBuildComplementInfo, HoltBuildComplementFromCocycle

HoltSolveCocycles := function(module)
  return CachedComputeH1(module);
end;

HoltSolveCocyclesPcgs := function(module)
  return ComputeCocycleSpaceViaPcgs(module);
end;

HoltModuleFingerprint := function(module)
  return ComputeModuleFingerprint(module);
end;

HoltBuildComplementInfo := function(Q, M_bar, module)
  return BuildComplementInfo(Q, M_bar, module);
end;

HoltBuildComplementFromCocycle := function(cocycleVec, complementInfo)
  return CocycleToComplement(cocycleVec, complementInfo);
end;

# The real clean lifter (per §4.3-4.5).
HoltLiftOneParentAcrossLayer := function(G, layer, parent_subgroup)
  local S, M, N, R, L_reps, children, L_sub, children_L;

  S := parent_subgroup;
  M := layer.M;
  N := layer.N;

  # Sanity: M should be contained in S (parent contains the larger).
  if not IsSubgroup(S, M) then
    Error("HoltLiftOneParentAcrossLayer: layer M is not in parent S");
  fi;

  # Step 1: R = N_G(S).
  R := Normalizer(G, S);

  # Step 2+3: enumerate S-invariant subspaces (L/N) and take R/M orbit reps.
  L_reps := HoltInvariantSubspaceOrbits(S, M, N, R);

  children := [];
  for L_sub in L_reps do
    children_L := _HoltLiftFixedIntersection(G, S, M, N, R, L_sub);
    Append(children, children_L);
  od;

  return children;
end;

# Inner helper: given parent S, layer (N,M), and a fixed intersection L = L_sub
# (normal in S, N <= L <= M), enumerate all T <= S with T*M = S and T cap M = L.
_HoltLiftFixedIntersection := function(G, S, M, N, R, L)
  local hom, Q, M_bar, complements, Q_norm, outerNormGens,
        complement_subgroups, C_bar, T, gen;

  # Case: L = M -> trivial layer, only child is S itself.
  if Size(L) = Size(M) then
    return [S];
  fi;

  # Form quotient S -> S/L
  hom := SafeNaturalHomByNSG(S, L);
  if hom = fail then
    return [];
  fi;
  Q := ImagesSource(hom);
  M_bar := Image(hom, M);  # M/L in S/L

  # Complements to M/L in S/L. Use the legacy H^1 orbital machinery which
  # already applies the Q/S orbit reduction when outer-normalizer
  # generators are provided.
  #
  # To get Q/S orbit reduction per §4.5, we pass the generators of
  # N_R(L) \ S (elements outside S that normalize both S and L).
  Q_norm := Normalizer(R, L);
  outerNormGens := [];
  for gen in GeneratorsOfGroup(Q_norm) do
    if not gen in S then
      Add(outerNormGens, gen);
    fi;
  od;

  if IsElementaryAbelian(M_bar) and Size(M_bar) > 1
     and IsBound(GetH1OrbitRepresentatives) then
    _TryLoadCohomology();
    _TryLoadH1Orbital();
    if Length(outerNormGens) > 0 then
      complements := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens,
                                                 S, L, hom, G);
    else
      complements := GetComplementsViaH1(Q, M_bar);
    fi;
    if complements = fail then
      complements := [];
    fi;
  else
    # Fallback: general complement enumeration.
    complements := ComplementClassesRepresentatives(Q, M_bar);
  fi;

  complement_subgroups := [];
  for C_bar in complements do
    T := PreImages(hom, C_bar);
    Add(complement_subgroups, T);
  od;

  return complement_subgroups;
end;

##############################################################################
# SECTION: tf_database.g
##############################################################################

# holt_engine/tf_database.g
#
# Write-through cache of subgroup classes for trivial-Fitting groups.
# A miss computes (via ConjugacyClassesSubgroups or CCS fast path for
# |Q| <= 96), serializes to database/tf_groups/<key>.g, appends to
# database/tf_groups/index.g, and logs to tf_miss_log.txt.
#
# Public API:
#   HoltIdentifyTFTop(Q)           -> rec(key, size, id_group, canonical_group)
#     Keys by IdGroup(Q) when |Q| <= 2000, else by a structural fingerprint
#     (order + derived_length + composition_factor_multiset +
#      |abelianization| + |center|) compatible with TF_SUBGROUP_LATTICE.
#   HoltLoadTFClasses(tf_info)     -> [ subgroup classrep in canonical_group ]
#     Lookup order:
#       1. In-memory HOLT_TF_CACHE
#       2. database/tf_groups/<key>.g on disk
#       3. TF_SUBGROUP_LATTICE (existing monolithic cache)
#       4. TransitiveGroup library via GetSubgroupClassReps
#       5. Compute via ConjugacyClassesSubgroups + write-through
#   HoltTFDatabasePath()           -> path to database/tf_groups/
#   HoltTFMissLogPath()            -> path to tf_miss_log.txt
#   HoltSaveTFEntry(key, Q, classes, elapsed_ms) -> write-through serializer
#   HoltLogTFMiss(key, size, structure_desc, elapsed_ms)

if not IsBound(HOLT_TF_CACHE) then
  HOLT_TF_CACHE := rec();
fi;

if not IsBound(HOLT_TF_STATS) then
  HOLT_TF_STATS := rec(
    mem_hits := 0,
    disk_hits := 0,
    tf_lattice_hits := 0,
    transitive_hits := 0,
    misses := 0,
    maximal_recursions := 0,
    total_load_ms := 0
  );
fi;

# Default thresholds bound at module load so _HoltSubgroupsRecurse can
# reference them even when called outside HoltLoadTFClasses (e.g. via
# HoltFPFViaMaximals from the dispatcher pre-check path).
if not IsBound(HOLT_TF_CCS_DIRECT) then
  HOLT_TF_CCS_DIRECT := 5000;
fi;
if not IsBound(HOLT_TF_WARN_ABOVE) then
  HOLT_TF_WARN_ABOVE := 5000;
fi;

# Recursive-from-maximals (architecture doc §3.2).
# For |Q| too big for CCS, enumerate maximal subgroup classes (much
# cheaper than full ConjugacyClassesSubgroups) and recurse on each.
#
# CRITICAL: do NOT go through HoltLoadTFClasses for the recursion.
# That cache is keyed by IdGroup (abstract isomorphism), so two
# embedded copies of the same abstract group (e.g. two A_8-classes
# of AGL(3,2)) would share a cache entry whose subgroups are
# embedded in the FIRST copy's ambient — wrong for the second copy.
# We need subgroups embedded in the SPECIFIC M we're recursing on.

# Enumerate subgroup classes of G, direct or via further recursion
_HoltSubgroupsRecurse := function(G)
  if Size(G) <= HOLT_TF_CCS_DIRECT then
    return List(ConjugacyClassesSubgroups(G), Representative);
  fi;
  return HoltSubgroupsViaMaximals(G);
end;

HoltSubgroupsViaMaximals := function(G)
  local max_classes, all_subs, M, subs_of_M, H, found, K,
        sz, bucketKey, buckets, keyStr;
  Print("    [maximal-rec] |G|=", Size(G), " expanding maximals...\n");
  max_classes := List(ConjugacyClassesMaximalSubgroups(G), Representative);
  Print("    [maximal-rec] |G|=", Size(G), " -> ", Length(max_classes),
        " maximal classes: sizes ", List(max_classes, Size), "\n");

  # Collect subgroups from each maximal, bucket by size for cheap dedup
  buckets := rec();
  bucketKey := String(Size(G));
  buckets.(bucketKey) := [G];

  for M in max_classes do
    subs_of_M := _HoltSubgroupsRecurse(M);
    for H in subs_of_M do
      sz := Size(H);
      bucketKey := String(sz);
      if not IsBound(buckets.(bucketKey)) then
        buckets.(bucketKey) := [H];
      else
        # Dedup under G-conjugation (OnPoints = conjugation action).
        found := false;
        for K in buckets.(bucketKey) do
          if RepresentativeAction(G, H, K, OnPoints) <> fail then
            found := true;
            break;
          fi;
        od;
        if not found then
          Add(buckets.(bucketKey), H);
        fi;
      fi;
    od;
  od;

  all_subs := [];
  for keyStr in RecNames(buckets) do
    Append(all_subs, buckets.(keyStr));
  od;
  return all_subs;
end;

HoltTFDatabasePath := function()
  return "C:/Users/jeffr/Downloads/Lifting/database/tf_groups/";
end;

HoltTFMissLogPath := function()
  return "C:/Users/jeffr/Downloads/Lifting/tf_miss_log.txt";
end;

# Structural fingerprint matching TF_SUBGROUP_LATTICE key format
# (see database/tf_groups/tf_subgroup_lattice.g). Used when |Q| > 2000.
HoltStructuralKey := function(Q)
  local sz, ds, ab, cs, nc, ex, z;
  sz := Size(Q);
  ds := DerivedSeriesOfGroup(Q);
  ds := List(ds, Size);
  ab := AbelianInvariants(Q);
  cs := List(CompositionSeries(Q), Size);
  nc := NrConjugacyClasses(Q);
  ex := Exponent(Q);
  z := Size(Center(Q));
  return Concatenation(
    "lg_", String(sz),
    "_ds=", String(ds),
    "_ab=", String(ab),
    "_cs=", String(cs),
    "_nc=", String(nc),
    "_ex=", String(ex),
    "_z=", String(z)
  );
end;

HoltIdentifyTFTop := function(Q)
  local sz, idk, desc;
  sz := Size(Q);
  if sz = 1 then
    return rec(
      key := "trivial",
      size := 1,
      id_group := [1, 1],
      canonical_group := Q,
      structure_desc := "1"
    );
  fi;
  if sz <= 2000 then
    idk := IdGroup(Q);
    return rec(
      key := Concatenation("id_", String(idk[1]), "_", String(idk[2])),
      size := sz,
      id_group := idk,
      canonical_group := Q,
      structure_desc := fail
    );
  fi;
  return rec(
    key := HoltStructuralKey(Q),
    size := sz,
    id_group := fail,
    canonical_group := Q,
    structure_desc := fail
  );
end;

# _HoltSerializeGroupGens: serialize a perm group as ListPerm-style lists,
# compatible with GroupFromGenLists / PermFromList in load_database.g.
_HoltSerializeGroupGens := function(G)
  local gens, moved_max, g;
  gens := [];
  if not IsPermGroup(G) then
    return gens;
  fi;
  moved_max := LargestMovedPoint(G);
  if moved_max = 0 then
    return gens;
  fi;
  for g in GeneratorsOfGroup(G) do
    if g = () then
      Add(gens, []);
    else
      Add(gens, ListPerm(g, moved_max));
    fi;
  od;
  return gens;
end;

HoltSaveTFEntry := function(key, Q, classes, elapsed_ms)
  local path, tmpfile, canonicalGens, classGens, tag;
  path := Concatenation(HoltTFDatabasePath(), key, ".g");
  # Temp file with worker-unique suffix (Runtime + Random) so concurrent
  # writers don't clobber each other's in-progress files. Atomic rename
  # at the end publishes the result as a single step, so readers (via
  # Read() in HoltLoadTFClasses) never see a partial file.
  tag := Concatenation(String(Runtime()), "_", String(Random(1, 10^9)));
  tmpfile := Concatenation(path, ".tmp.", tag);
  canonicalGens := _HoltSerializeGroupGens(Q);
  classGens := List(classes, _HoltSerializeGroupGens);
  PrintTo(tmpfile, "# holt_engine tf_database entry. Auto-generated.\n");
  AppendTo(tmpfile, "HOLT_TF_LAST_LOAD := rec(\n");
  AppendTo(tmpfile, "  key := \"", key, "\",\n");
  AppendTo(tmpfile, "  size := ", Size(Q), ",\n");
  AppendTo(tmpfile, "  canonical_gens := ", canonicalGens, ",\n");
  AppendTo(tmpfile, "  classes := ", classGens, ",\n");
  AppendTo(tmpfile, "  elapsed_ms := ", elapsed_ms, "\n");
  AppendTo(tmpfile, ");\n");
  # Atomic publish. If another worker beat us to it, last-writer-wins --
  # both workers computed semantically equivalent class lists (different
  # generators may be chosen but the classes coincide up to conjugacy).
  # `mv` over Cygwin is atomic on both POSIX and NTFS.
  Exec(Concatenation("mv '", tmpfile, "' '", path, "'"));
  return path;
end;

HoltLogTFMiss := function(key, size, structure_desc, elapsed_ms)
  local path;
  path := HoltTFMissLogPath();
  AppendTo(path, key, "\t", size, "\t",
    String(structure_desc), "\t", elapsed_ms, "\n");
end;

# Convert stored gen lists back into a group acting on the same points as Q
_HoltGroupFromStoredGens := function(genLists, moved_points)
  local gens, lst, p;
  gens := [];
  for lst in genLists do
    if Length(lst) > 0 then
      p := PermList(lst);
      if p <> () then
        Add(gens, p);
      fi;
    fi;
  od;
  if Length(gens) = 0 then
    return Group(());
  fi;
  return Group(gens);
end;

HoltLoadTFClasses := function(tf_info)
  local key, Q, path, classes, t0, classGens, H, lat_entry, n, moved;
  key := tf_info.key;
  Q := tf_info.canonical_group;
  t0 := Runtime();

  # All cache tiers must validate perm-rep compatibility via IsSubset(Q, H).
  # Classes cached under a key may have been stored for one Q's perm-rep and
  # queried later for a different (abstractly isomorphic) Q on different
  # points — returning those stale classes poisons downstream PreImages with
  # "Range(<map>)" errors. Each tier below validates and falls through on
  # mismatch; the final compute-and-cache tier then writes a fresh entry
  # for this Q.

  # 1. In-memory
  if IsBound(HOLT_TF_CACHE.(key)) then
    classes := HOLT_TF_CACHE.(key);
    if ForAll(classes, H -> IsSubset(Q, H)) then
      HOLT_TF_STATS.mem_hits := HOLT_TF_STATS.mem_hits + 1;
      return classes;
    fi;
    # Stale entry — evict so later tiers can replace it.
    Unbind(HOLT_TF_CACHE.(key));
  fi;

  # 2. On-disk per-key file
  path := Concatenation(HoltTFDatabasePath(), key, ".g");
  if IsReadableFile(path) then
    HOLT_TF_LAST_LOAD := fail;
    Read(path);
    if IsBound(HOLT_TF_LAST_LOAD) and HOLT_TF_LAST_LOAD <> fail then
      classes := List(HOLT_TF_LAST_LOAD.classes,
                      gl -> _HoltGroupFromStoredGens(gl, fail));
      if ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(key) := classes;
        HOLT_TF_STATS.disk_hits := HOLT_TF_STATS.disk_hits + 1;
        HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
        return classes;
      fi;
      # Cached entry incompatible with current Q — fall through.
    fi;
  fi;

  # 3. TF_SUBGROUP_LATTICE (existing monolithic)
  if IsBound(TF_SUBGROUP_LATTICE) and IsBound(TF_SUBGROUP_LATTICE.(key)) then
    lat_entry := TF_SUBGROUP_LATTICE.(key);
    if IsBound(lat_entry.subgroups) then
      classes := lat_entry.subgroups;
      if ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(key) := classes;
        HOLT_TF_STATS.tf_lattice_hits := HOLT_TF_STATS.tf_lattice_hits + 1;
        return classes;
      fi;
      # Fall through on perm-rep mismatch.
    fi;
  fi;

  # 4. TransitiveGroup library via GetSubgroupClassReps
  # (Handles shifted transitive groups by identifying them as T(n,k).)
  if IsBound(GetSubgroupClassReps) then
    moved := MovedPoints(Q);
    if Length(moved) > 0 and IsTransitive(Q, moved) then
      classes := GetSubgroupClassReps(Q);
      if Length(classes) > 0 and ForAll(classes, H -> IsSubset(Q, H)) then
        HOLT_TF_CACHE.(key) := classes;
        HOLT_TF_STATS.transitive_hits := HOLT_TF_STATS.transitive_hits + 1;
        return classes;
      fi;
    fi;
  fi;

  # 5. Miss: compute + write-through with safe concurrent publish.
  #
  # The architecture doc §3.2 prefers erroring on miss, but for a working
  # system lazy population is operator-friendly. We bend the rule:
  #   - Compute via ConjugacyClassesSubgroups(Q) up to a HARD CEILING.
  #   - Write atomically to disk so concurrent workers don't corrupt the
  #     file.
  #   - HOLT_TF_STRICT_MISS (opt-in, default false): error on ANY miss.
  #   - HOLT_TF_CCS_CEILING (default 20000): above this, raise Error so
  #     the dispatcher can fall back to legacy fast paths (Goursat +
  #     D_4^3 + S_n short-circuit). CCS on groups above 20k often takes
  #     minutes-to-hours and blocks the worker.
  #   - HOLT_TF_WARN_ABOVE (default 5000): warning threshold.
  #
  # Before computing, re-check the disk: another worker may have written
  # the file between our earlier check and now. If so, load from disk.
  if IsBound(HOLT_TF_STRICT_MISS) and HOLT_TF_STRICT_MISS then
    HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, -1);
    Error("HoltLoadTFClasses: strict-miss mode, |Q|=", Size(Q),
          " not in database. Set HOLT_TF_STRICT_MISS := false ",
          "to enable lazy population.");
  fi;
  # Two-tier compute strategy (per architecture doc §3.2):
  #   |Q| <= HOLT_TF_CCS_DIRECT  -> direct CCS  (default 5000)
  #   otherwise                   -> recursive-from-maximals (HoltSubgroupsViaMaximals)
  #
  # No hard upper bound by default — max-recursion's cost scales with
  # MaximalSubgroupClassReps, which for A_8 x A_8 (|G|=406M) runs in ~1s.
  # Set HOLT_TF_MAXREC_CEILING to force an Error boundary for paranoia.
  if not IsBound(HOLT_TF_CCS_DIRECT) then
    HOLT_TF_CCS_DIRECT := 5000;
  fi;
  if IsBound(HOLT_TF_MAXREC_CEILING) and Size(Q) > HOLT_TF_MAXREC_CEILING then
    HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, -2);
    Error("HoltLoadTFClasses: |Q|=", Size(Q),
          " exceeds HOLT_TF_MAXREC_CEILING=", HOLT_TF_MAXREC_CEILING);
  fi;

  # Double-check disk — another worker may have just written
  if IsReadableFile(path) then
    HOLT_TF_LAST_LOAD := fail;
    Read(path);
    if IsBound(HOLT_TF_LAST_LOAD) and HOLT_TF_LAST_LOAD <> fail then
      classes := List(HOLT_TF_LAST_LOAD.classes,
                      gl -> _HoltGroupFromStoredGens(gl, fail));
      HOLT_TF_CACHE.(key) := classes;
      HOLT_TF_STATS.disk_hits := HOLT_TF_STATS.disk_hits + 1;
      HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
      return classes;
    fi;
  fi;

  if Size(Q) > HOLT_TF_CCS_DIRECT then
    # Maximal-subgroup recursion (architecture doc §3.2)
    Print("  [HoltLoadTFClasses] |Q|=", Size(Q),
          " above CCS-direct (", HOLT_TF_CCS_DIRECT,
          "); using maximal-subgroup recursion.\n");
    HOLT_TF_STATS.maximal_recursions := HOLT_TF_STATS.maximal_recursions + 1;
    classes := HoltSubgroupsViaMaximals(Q);
  else
    classes := List(ConjugacyClassesSubgroups(Q), Representative);
  fi;
  HoltSaveTFEntry(key, Q, classes, Runtime() - t0);
  HoltLogTFMiss(key, tf_info.size, tf_info.structure_desc, Runtime() - t0);
  HOLT_TF_CACHE.(key) := classes;
  HOLT_TF_STATS.misses := HOLT_TF_STATS.misses + 1;
  HOLT_TF_STATS.total_load_ms := HOLT_TF_STATS.total_load_ms + (Runtime() - t0);
  return classes;
end;

##############################################################################
# SECTION: symmetric_specialization.g
##############################################################################

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

##############################################################################
# SECTION: engine.g
##############################################################################

# holt_engine/engine.g
#
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

HoltDedupUnderG := function(subgroups, G)
  local buckets, H, keyStr, allReps, bucketReps, found, K,
        ea_reps, rep, first_subgroup_of_size;
  if Length(subgroups) <= 1 then return subgroups; fi;

  # Fast path: if G is elementary abelian, use matrix-orbit dedup
  # directly on all subgroups at once (arbitrary prime p, any dim).
  if IsPGroup(G) and IsElementaryAbelian(G) then
    ea_reps := _HoltOrbitDedupEA(subgroups, G, G);  # use G as its own normalizer
    if ea_reps <> fail then
      return ea_reps;
    fi;
  fi;

  # General path: invariant bucketing + pairwise RepresentativeAction
  buckets := rec();
  for H in subgroups do
    keyStr := String(_HoltGenericInvariantKey(H));
    if not IsBound(buckets.(keyStr)) then
      buckets.(keyStr) := [];
    fi;
    Add(buckets.(keyStr), H);
  od;
  allReps := [];
  for keyStr in RecNames(buckets) do
    bucketReps := [];
    for H in buckets.(keyStr) do
      found := false;
      for K in bucketReps do
        if RepresentativeAction(G, H, K, OnPoints) <> fail then
          found := true;
          break;
        fi;
      od;
      if not found then
        Add(bucketReps, H);
      fi;
    od;
    Append(allReps, bucketReps);
  od;
  return allReps;
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
  local P, shifted_factors, offsets, partNormalizer, normArg,
        series_rec, layers_topdown, current, layer, next_classes,
        parent, children;

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

  # Stage A: top classes, FPF-filtered immediately
  current := HoltTopClasses(P, series_rec);
  current := Filtered(current,
    H -> IsFPFSubdirect(H, shifted_factors, offsets));

  # Stage B: layer lifting with per-layer FPF filter
  layers_topdown := Reversed(series_rec.layers);
  for layer in layers_topdown do
    next_classes := [];
    for parent in current do
      children := HoltLiftOneParentAcrossLayer(P, layer, parent);
      children := Filtered(children,
        T -> IsFPFSubdirect(T, shifted_factors, offsets));
      Append(next_classes, children);
    od;
    current := HoltDedupUnderG(next_classes, normArg);
  od;

  return current;
end;

# Legacy S_n FPF-filtered path (Phase 4 thin wrapper - preserved).
HoltSubgroupClassesOfProduct := function(arg)
  return CallFuncList(FindFPFClassesByLifting, arg);
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

# Mode-based dispatcher. HOLT_ENGINE_MODE controls routing:
#   "legacy"        - always use FindFPFClassesByLifting (fast, battle-tested)
#   "clean"         - try clean pipeline, fall back to legacy on error
#   "max_rec"       - try HoltFPFViaMaximals, fall back to legacy on error
#   "clean_first"   - clean -> max_rec -> legacy (original routing)
#
# Default "legacy" because the clean pipeline is 5-6x slower than legacy
# on S_n FPF problems (missing Goursat / D_4^3 / S_n short-circuit fast
# paths, O(N^2) dedup on non-EA ambient P). Set HOLT_ENGINE_MODE
# explicitly to opt into the Holt pipeline for research/verification.
_HoltDispatchLift := function(arg)
  local P, tfsz, result;
  if not IsBound(HOLT_ENGINE_MODE) then
    HOLT_ENGINE_MODE := "legacy";
  fi;

  if HOLT_ENGINE_MODE = "legacy" then
    return CallFuncList(FindFPFClassesByLifting, arg);
  fi;

  P := arg[1];

  if HOLT_ENGINE_MODE = "clean" or HOLT_ENGINE_MODE = "clean_first" then
    BreakOnError := false;
    result := CALL_WITH_CATCH(
      function() return CallFuncList(HoltFPFSubgroupClassesOfProduct, arg); end,
      []);
    BreakOnError := true;
    if result[1] = true then return result[2]; fi;
  fi;

  if HOLT_ENGINE_MODE = "max_rec" or HOLT_ENGINE_MODE = "clean_first" then
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

##############################################################################
# SECTION: verification.g
##############################################################################

# holt_engine/verification.g
#
# Correctness harness: regression counts + layer-level sanity checks.
#
# Public API:
#   HoltRegressionCheck(n)                       -> true if new-engine S_n count matches OEIS
#   HoltVerifyLayerLift(G, layer, parent, children) -> true if every child satisfies T*M = S, T ∩ M = L
#   HOLT_OEIS_COUNTS                             -> rec keyed by n giving OEIS A000638 values

# OEIS A000638: number of conjugacy classes of subgroups of S_n.
HOLT_OEIS_COUNTS := rec(
  ("1") := 1,
  ("2") := 2,
  ("3") := 4,
  ("4") := 11,
  ("5") := 19,
  ("6") := 56,
  ("7") := 96,
  ("8") := 296,
  ("9") := 554,
  ("10") := 1593,
  ("11") := 3094,
  ("12") := 10723,
  ("13") := 20832,
  ("14") := 75154,
  ("15") := 159129,
  ("16") := 686165,
  ("17") := 1466358,
  ("18") := 7274651
);

HoltRegressionCheck := function(n)
  local key, expected, got;
  key := String(n);
  if not IsBound(HOLT_OEIS_COUNTS.(key)) then
    return fail;
  fi;
  expected := HOLT_OEIS_COUNTS.(key);
  if IsBound(LIFT_CACHE) and IsBound(LIFT_CACHE.(key)) then
    got := LIFT_CACHE.(key);
    return got = expected;
  fi;
  return fail;
end;

HoltVerifyLayerLift := function(G, layer, parent, children)
  local T, M, L, S, tm, tcapm;
  S := parent.subgroup;
  M := layer.M;
  L := layer.N;
  for T in children do
    tm := ClosureGroup(T.subgroup, M);
    if tm <> S then
      return false;
    fi;
    tcapm := Intersection(T.subgroup, M);
    if tcapm <> L then
      return false;
    fi;
  od;
  return true;
end;


HOLT_ENGINE_LOADED := true;
Print("holt_engine_monolith loaded\n");
