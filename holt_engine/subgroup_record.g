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
