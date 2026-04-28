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
