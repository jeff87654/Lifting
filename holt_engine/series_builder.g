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
