LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_s16_partition.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

# Warm up S2..S10 counts (needed for inherited)
CountAllConjugacyClassesFast(10);

# Compute [4,4,4,2,2] of S_14 partition (wait we want S_16)
HOLT_ENGINE_MODE := "clean_first";

# With iso-transport ON (default, as ran)
HOLT_DISABLE_ISO_TRANSPORT := false;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r1 := FindFPFClassesForPartition(16, [8,4,4]);
e1 := (Runtime() - t0) / 1000.0;
Print("\n[iso ON] [8,4,4] = ", Length(r1), " in ", e1, "s\n");

# With iso-transport OFF
HOLT_DISABLE_ISO_TRANSPORT := true;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
t0 := Runtime();
r2 := FindFPFClassesForPartition(16, [8,4,4]);
e2 := (Runtime() - t0) / 1000.0;
Print("\n[iso OFF] [8,4,4] = ", Length(r2), " in ", e2, "s\n");

# Compare
if Length(r1) = Length(r2) then
  Print("MATCH: both ", Length(r1), "\n");
else
  Print("DIFFER: iso-on=", Length(r1), ", iso-off=", Length(r2), "\n");
fi;

LogTo();
QUIT;
