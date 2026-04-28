LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_s17_slow_combo_holt.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_HOLT_ENGINE := true;
HOLT_DISABLE_ISO_TRANSPORT := true;

# Force Holt clean pipeline (bypass S_n fast-path detector)
HOLT_ENGINE_MODE := "clean";

# Clear caches
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

# Build P = T(2,1) x T(5,5) x T(5,5) x T(5,5) shifted into S_17 blocks
f1 := TransitiveGroup(2,1);
f2 := TransitiveGroup(5,5);
f3 := TransitiveGroup(5,5);
f4 := TransitiveGroup(5,5);
currentFactors := [f1, f2, f3, f4];

shifted := [];
offs := [];
off := 0;
for k in [1..Length(currentFactors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(currentFactors[k], off));
    off := off + NrMovedPoints(currentFactors[k]);
od;
Print("factors = ", currentFactors, "\n");
Print("offsets = ", offs, "\n");

P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Print("|P| = ", Size(P), "\n");

Pt := RadicalGroup(P);
Print("|Pt| = ", Size(Pt), ", |Q| = ", Size(P)/Size(Pt), "\n");

# Build per-combo normalizer (same as worker 42 used)
partition := [5,5,5,2];
n := 17;
Npart := BuildPerComboNormalizer(partition, currentFactors, n);
Print("|Npart| (per-combo) = ", Size(Npart), "\n");

CURRENT_BLOCK_RANGES := [[1,2],[3,7],[8,12],[13,17]];

Print("\n=== Running HoltFPFSubgroupClassesOfProduct (clean pipeline) ===\n");
Print("Threshold HOLT_TF_CCS_DIRECT = ", HOLT_TF_CCS_DIRECT, "\n");
Print("|Q| = ", Size(P)/Size(Pt), " > ", HOLT_TF_CCS_DIRECT,
      " -> HoltTopSubgroupsByMaximals will be used\n\n");

t0 := Runtime();
result_pack := CALL_WITH_CATCH(function()
  return HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
end, []);
t := (Runtime() - t0) / 1000.0;

Print("\nElapsed: ", t, "s\n");
if result_pack[1] then
  Print("Result count: ", Length(result_pack[2]), "\n");
else
  Print("Error (caught): ", result_pack, "\n");
fi;

Print("\n=== Summary ===\n");
Print("Legacy baseline (worker 42): 5346s on last layer alone (89 min combo-total)\n");
Print("Expected correct count (from worker 42 log): 32 FPF classes for this combo\n");
Print("Holt clean + HoltTopSubgroupsByMaximals: ", t, "s\n");

LogTo();
QUIT;
