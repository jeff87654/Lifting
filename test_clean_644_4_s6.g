LogTo("C:/Users/jeffr/Downloads/Lifting/test_clean_644_4_s6.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";  # force Holt clean, bypass legacy fast-path
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Force a clean run via _HoltDispatchLift for [T(6,16), T(4,3)^3] in [6,4,4,4]
part := [6,4,4,4];
factors := [TransitiveGroup(6,16), TransitiveGroup(4,3),
            TransitiveGroup(4,3), TransitiveGroup(4,3)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Npart := BuildPerComboNormalizer(part, factors, 18);
CURRENT_BLOCK_RANGES := [[1,6],[7,10],[11,14],[15,18]];

# Force HOLT clean path: Set _HoltIsLegacyFastPathCase to return false for this
# so the dispatcher routes to Holt clean instead of S_n legacy.
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
clean := _HoltDispatchLift(P, shifted, offs, Npart);
t := (Runtime() - t0)/1000.0;
Print("\nClean dispatcher result: ", Length(clean), " in ", t, "s\n");
Print("Disk W810-813 wrote: 3496\n");
Print("Delta: ", Length(clean) - 3496, "\n");

LogTo();
QUIT;
