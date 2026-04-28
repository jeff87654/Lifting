LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/smoke_s11_no_sn_fastpath.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_DISABLE_ISO_TRANSPORT := true;  # gates all 3 iso-transport paths now
# Clean_first mode so the modified detector routes all but D_4^3 / small /
# Goursat combos through the clean pipeline.
HOLT_ENGINE_MODE := "clean_first";

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
r := CountAllConjugacyClassesFast(11);
t := (Runtime() - t0) / 1000.0;
Print("\n=== S_11 RESULT: ", r, " (expected 3094) in ", t, "s ===\n");
if r = 3094 then
  Print("PASS\n");
else
  Print("FAIL - off by ", r - 3094, "\n");
fi;
LogTo();
QUIT;
