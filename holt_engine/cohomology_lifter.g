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

# FPF-context globals. Set by HoltFPFSubgroupClassesOfProduct before entering
# the layer loop; read by _HoltLiftFixedIntersection's FPF-impossibility
# pruner. When _HOLT_LIFT_FACTORS is fail, no FPF pruning happens (generic
# HoltSubgroupClassesOfGroup path). Ported from legacy lifting_algorithm.g:1600.
if not IsBound(_HOLT_LIFT_FACTORS) then _HOLT_LIFT_FACTORS := fail; fi;
if not IsBound(_HOLT_LIFT_OFFSETS) then _HOLT_LIFT_OFFSETS := fail; fi;

# Arithmetic necessary condition for a subgroup of order `comp_order` to be
# FPF on a set of disjoint factor orbits: for every factor f, the orbit size
# NrMovedPoints(f) must divide comp_order (otherwise no transitive action is
# possible on that orbit). Very cheap; catches a large fraction of
# complement-enumeration overhead on FPF-heavy combos.
_HoltFPFCompatibleOrder := function(comp_order, factors)
  local f;
  if factors = fail then return true; fi;
  if IsBound(HOLT_DISABLE_FPF_PRUNE) and HOLT_DISABLE_FPF_PRUNE then
    return true;  # diagnostic: disable the pruner
  fi;
  for f in factors do
    if comp_order mod NrMovedPoints(f) <> 0 then
      return false;
    fi;
  od;
  return true;
end;

# The real clean lifter (per §4.3-4.5).
#
# Accepts an optional 4th argument `parent_normalizer` which should be
# N_G(S_parent) — the normalizer of the parent subgroup in the layer ABOVE
# S, computed at the previous lift step. Correctness: for every child T
# with T*M = S (M G-normal), N_G(T) ⊆ N_G(S), and N_G(S) ⊆ N_G(S_parent)
# since S ⊇ M and S_parent ⊇ M. So `Normalizer(parent_normalizer, S)` ==
# N_G(S). Using the smaller parent_normalizer as the search domain is
# typically 10-100x faster than starting from G.
#
# When parent_normalizer is omitted or fail, falls back to Normalizer(G, S).
HoltLiftOneParentAcrossLayer := function(arg)
  local G, layer, parent_subgroup, parent_norm,
        S, M, N, R, L_reps, children, L_sub, children_L, searchDomain;

  G := arg[1];
  layer := arg[2];
  parent_subgroup := arg[3];
  if Length(arg) >= 4 and arg[4] <> fail then
    parent_norm := arg[4];
  else
    parent_norm := fail;
  fi;

  S := parent_subgroup;
  M := layer.M;
  N := layer.N;

  # Sanity: M should be contained in S (parent contains the larger).
  if not IsSubgroup(S, M) then
    Error("HoltLiftOneParentAcrossLayer: layer M is not in parent S");
  fi;

  # Step 1: R = N_G(S). If parent_norm was passed, use it as the search
  # domain instead of G.
  if parent_norm = fail then
    searchDomain := G;
  else
    searchDomain := parent_norm;
  fi;
  R := Normalizer(searchDomain, S);

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
        complement_subgroups, C_bar, T, gen, comp_order;

  # Case: L = M -> trivial layer, only child is S itself.
  if Size(L) = Size(M) then
    return [S];
  fi;

  # FPF-impossibility prune (ported from lifting_algorithm.g:1600).
  # Any T with T*M = S and T cap M = L has |T| = |S|*|L|/|M|. If any factor
  # orbit size doesn't divide this |T|, no subgroup with this intersection
  # can be FPF → skip the whole complement enumeration.
  comp_order := Size(S) * Size(L) / Size(M);
  if not _HoltFPFCompatibleOrder(comp_order, _HOLT_LIFT_FACTORS) then
    return [];
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
  elif Size(M_bar) = 1 then
    # Trivial quotient — only the image Q itself is a "complement".
    complements := [Q];
  else
    # M2 discipline boundary: M_bar must be elementary abelian (M/L with
    # M/N EA and L in [N,M]). Non-EA M_bar indicates a non-abelian chief
    # factor leaked past the TF-top split, which is a refinement bug.
    # Error so the dispatcher's CALL_WITH_CATCH can route to legacy.
    Error("_HoltLiftFixedIntersection: M_bar not elementary abelian, ",
          "|M_bar|=", Size(M_bar), " — non-EA chief factor leaked into ",
          "the lifter");
  fi;

  complement_subgroups := [];
  for C_bar in complements do
    T := PreImages(hom, C_bar);
    Add(complement_subgroups, T);
  od;

  return complement_subgroups;
end;
