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
