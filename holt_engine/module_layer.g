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
# M2 discipline boundary: M/N MUST be elementary abelian by the time it
# reaches this routine. If it isn't, HoltExtractLayers / RefineChiefSeries
# missed a refinement step upstream. Raise Error so the dispatcher's
# CALL_WITH_CATCH can fall back to legacy instead of silently using an
# O(N^2) pairwise dedup on big buckets.

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
    Error("HoltInvariantSubspaceOrbits: M/N quotient undefined, |M|=",
          Size(M), " |N|=", Size(N),
          " — HoltBuildLiftSeries should have caught this");
  fi;

  V := ImagesSource(hom);
  if not IsPGroup(V) or not IsElementaryAbelian(V) then
    Error("HoltInvariantSubspaceOrbits: M/N not elementary abelian, |M/N|=",
          Size(V), " — refinement failed upstream");
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
