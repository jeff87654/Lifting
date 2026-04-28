LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diag_iso_844_mode.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;

RunOne := function(mode, iso)
  local f1, f2, f3, shifted, offs, off, k, P, Npart, partition,
        currentFactors, t0, t, fpf, outdir;

  HOLT_DISABLE_ISO_TRANSPORT := not iso;
  HOLT_ENGINE_MODE := mode;
  FPF_SUBDIRECT_CACHE := rec();
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  HOLT_TF_CACHE := rec();

  # Call through FindFPFClassesForPartition with a fake "only this combo" path?
  # Cleanest: call IterateCombinations via FindFPFClassesForPartition but
  # restrict. For simplicity, call FindFPFClassesByLifting / HoltFPFSubgroupClassesOfProduct
  # according to mode using the actual combo setup.

  f1 := TransitiveGroup(8,17);
  f2 := TransitiveGroup(4,2);
  f3 := TransitiveGroup(4,1);
  currentFactors := [f1, f2, f3];
  partition := [8,4,4];

  shifted := [];
  offs := [];
  off := 0;
  for k in [1..Length(currentFactors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(currentFactors[k], off));
    off := off + NrMovedPoints(currentFactors[k]);
  od;
  P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
  SetSize(P, Product(List(shifted, Size)));
  Npart := BuildPerComboNormalizer(partition, currentFactors, 16);
  CURRENT_BLOCK_RANGES := [[1,8],[9,12],[13,16]];

  t0 := Runtime();
  fpf := _HoltDispatchLift(P, shifted, offs, Npart);
  t := (Runtime() - t0)/1000.0;
  Print("mode=", mode, " iso=", iso, ": ", Length(fpf), " in ", t, "s\n");
  return Length(fpf);
end;

Print("\n=== 4 combinations ===\n");
RunOne("clean", false);
RunOne("clean", true);
RunOne("clean_first", false);
RunOne("clean_first", true);
RunOne("legacy", true);

LogTo();
QUIT;
