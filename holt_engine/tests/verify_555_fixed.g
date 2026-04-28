LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_555_fixed.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";

CountAllConjugacyClassesFast(10);

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t0 := Runtime();
res := FindFPFClassesForPartition(15, [5,5,5]);
_e := (Runtime() - _t0)/1000.0;
Print("\n=== [5,5,5] clean_first (FIXED filter) = ", Length(res), " classes in ", _e, "s ===\n");

LogTo();
QUIT;
