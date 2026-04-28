LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_555_all_off.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

HOLT_DISABLE_BLOCKNORM := true;
HOLT_DISABLE_RICH_DEDUP := true;
_HOLT_RICH_BUCKET_THRESHOLD := 10^9;   # effectively disables M7 progressive refinement

Print("BLOCKNORM_DISABLED = ", HOLT_DISABLE_BLOCKNORM, "\n");
Print("RICH_DEDUP_DISABLED = ", HOLT_DISABLE_RICH_DEDUP, "\n");

CountAllConjugacyClassesFast(10);

HOLT_ENGINE_MODE := "clean_first";
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t0 := Runtime();
res := FindFPFClassesForPartition(15, [5,5,5]);
_e := (Runtime() - _t0)/1000.0;
Print("\n=== [5,5,5] clean_first w/o M6 w/o M7 = ", Length(res), " classes in ", _e, "s ===\n");

LogTo();
QUIT;
