LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_555_per_combo.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

# warm up
CountAllConjugacyClassesFast(10);

RunOneCombo := function(mode, combo_tuple)
  local T1, T2, T3, P, shifted, offsets, Npart, res, _t0, _e;
  HOLT_ENGINE_MODE := mode;
  T1 := TransitiveGroup(5, combo_tuple[1]);
  T2 := ShiftGroup(TransitiveGroup(5, combo_tuple[2]), 5);
  T3 := ShiftGroup(TransitiveGroup(5, combo_tuple[3]), 10);
  P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                            GeneratorsOfGroup(T3)));
  shifted := [T1, T2, T3];
  offsets := [0, 5, 10];
  Npart := SymmetricGroup(15);
  CURRENT_BLOCK_RANGES := [[1,5],[6,10],[11,15]];
  if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  _t0 := Runtime();
  res := _HoltDispatchLift(P, shifted, offsets, Npart);
  _e := (Runtime() - _t0)/1000.0;
  return rec(n := Length(res), t := _e);
end;

# Per-combo: iterate (a,b,c) with a<=b<=c in [1..5]
combos := [];
for a in [1..5] do for b in [a..5] do for c in [b..5] do
  Add(combos, [a,b,c]);
od; od; od;

Print("Testing ", Length(combos), " combos with clean_first vs legacy\n\n");
Print("combo\t\tclean_first\tlegacy\tdelta\n");

total_cf := 0; total_lg := 0;
for combo in combos do
  r_cf := RunOneCombo("clean_first", combo);
  r_lg := RunOneCombo("legacy", combo);
  total_cf := total_cf + r_cf.n;
  total_lg := total_lg + r_lg.n;
  if r_cf.n <> r_lg.n then
    Print("[5,", combo[1], "]_[5,", combo[2], "]_[5,", combo[3], "]",
          "\tCLEAN=", r_cf.n, "\tLEGACY=", r_lg.n,
          "\tDELTA=", r_lg.n - r_cf.n, "\n");
  fi;
od;

Print("\nTotal clean_first: ", total_cf, "\n");
Print("Total legacy: ", total_lg, "\n");
Print("Difference: ", total_lg - total_cf, "\n");

LogTo();
QUIT;
