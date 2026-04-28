LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_s16_862_v2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
RESTART_AFTER_SECONDS := 0;
CountAllConjugacyClassesFast(10);

HOLT_DISABLE_ISO_TRANSPORT := true;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
t0 := Runtime();
r2 := FindFPFClassesForPartition(16, [8,6,2]);
e2 := (Runtime() - t0) / 1000.0;
Print("\n[iso OFF] [8,6,2] = ", Length(r2), " in ", e2, "s (expected 29440)\n");
if Length(r2) = 29440 then
  Print("CORRECT -> iso-transport WAS the bug\n");
elif Length(r2) = 29439 then
  Print("STILL WRONG -> bug is not iso-transport\n");
else
  Print("UNEXPECTED: ", Length(r2), "\n");
fi;
LogTo();
QUIT;
