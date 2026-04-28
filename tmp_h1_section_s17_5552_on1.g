
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_h1_section_s17_5552_on1.log");
H1_OUTER_SECTION_ACTION := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";
HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;
HOLT_UF_INDEX_BUCKET_MIN := 40;
BlockRangesFromPartition := function(partition)
  local ranges, start, d;
  ranges := [];
  start := 1;
  for d in partition do
    Add(ranges, [start, start + d - 1]);
    start := start + d;
  od;
  return ranges;
end;
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
  CURRENT_BLOCK_RANGES := BlockRangesFromPartition(partition);
  return [P, shifted, offs, Nfull];
end;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
ResetH1OrbitalStats();
pack := BuildCombo();
Print("CASE s17_5552_on1 section=", H1_OUTER_SECTION_ACTION,
      " |P|=", Size(pack[1]), " |N|=", Size(pack[4]), "\n");
t0 := Runtime();
res := HoltFPFSubgroupClassesOfProduct(pack[1], pack[2], pack[3], pack[4]);
elapsed := Runtime() - t0;
Print("RESULT s17_5552_on1 count=", Length(res), " elapsed_ms=", elapsed, "\n");
PrintH1OrbitalStats();
LogTo();
QUIT;
