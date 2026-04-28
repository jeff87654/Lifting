LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_555_m6off.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_DISABLE_BLOCKNORM := false;  # disable M6
Print("HOLT_DISABLE_BLOCKNORM = ", HOLT_DISABLE_BLOCKNORM, "\n");

CountAllConjugacyClassesFast(10);

HOLT_ENGINE_MODE := "clean_first";
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t0 := Runtime();
res := FindFPFClassesForPartition(15, [5,5,5]);
_e := (Runtime() - _t0)/1000.0;
Print("\n=== [5,5,5] clean_first w/o M6 = ", Length(res), " classes in ", _e, "s ===\n");

LogTo();
QUIT;
