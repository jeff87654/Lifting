LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/bench_m8_555.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

CountAllConjugacyClassesFast(10);

# Baseline (M8 disabled): pairwise RA inside buckets
HOLT_DISABLE_CANON_DEDUP := true;
HOLT_ENGINE_MODE := "clean_first";
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r_base := FindFPFClassesForPartition(15, [5,5,5]);
e_base := (Runtime() - t0) / 1000.0;
Print("\n=== BASELINE [5,5,5] (no M8) = ", Length(r_base), " classes in ", e_base, "s ===\n");

# With M8
HOLT_DISABLE_CANON_DEDUP := false;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r_m8 := FindFPFClassesForPartition(15, [5,5,5]);
e_m8 := (Runtime() - t0) / 1000.0;
Print("\n=== M8 [5,5,5] = ", Length(r_m8), " classes in ", e_m8, "s ===\n");

Print("\n=== SUMMARY ===\n");
Print("baseline: ", Length(r_base), " in ", e_base, "s\n");
Print("M8      : ", Length(r_m8), " in ", e_m8, "s\n");
Print("speedup : ", e_base/e_m8, "x\n");
if Length(r_base) = Length(r_m8) and Length(r_m8) = 155 then
  Print("CORRECT (both 155)\n");
else
  Print("MISMATCH: base=", Length(r_base), " m8=", Length(r_m8), " expected 155\n");
fi;

LogTo();
QUIT;
