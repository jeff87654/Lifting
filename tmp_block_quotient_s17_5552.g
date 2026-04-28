
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_block_quotient_s17_5552.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";
BuildCombo := function()
  local partition, currentFactors, shifted, offs, off, k, P, Nfull;
  partition := [5,5,5,2];
  currentFactors := [TransitiveGroup(5,5), TransitiveGroup(5,5), TransitiveGroup(5,5), TransitiveGroup(2,1)];
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
  Nfull := BuildConjugacyTestGroup(17, partition);
  CURRENT_BLOCK_RANGES := [[1,5],[6,10],[11,15],[16,17]];
  return [P, shifted, offs, Nfull];
end;
RunOne := function(label, disable)
  local pack, t0, r, t;
  FPF_SUBDIRECT_CACHE := rec();
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
  HOLT_DISABLE_BLOCK_QUOTIENT_DEDUP := disable;
  HOLT_UF_INDEX_BUCKET_MIN := 40;
  pack := BuildCombo();
  Print("RUN ", label, " |P|=", Size(pack[1]), " |Nfull|=", Size(pack[4]), "\n");
  t0 := Runtime();
  r := HoltFPFSubgroupClassesOfProduct(pack[1], pack[2], pack[3], pack[4]);
  t := (Runtime() - t0) / 1000.0;
  Print(label, " count=", Length(r), " time=", t, "s\n");
end;
RunOne("disabled", true);
RunOne("enabled", false);
LogTo();
QUIT;
