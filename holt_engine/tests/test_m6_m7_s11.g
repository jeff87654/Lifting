LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_m6_m7_s11.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";

# Warmup: load S2..S10 caches.
CountAllConjugacyClassesFast(10);

# Clear caches so S11 is fresh timing.
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE_S11_ONLY := true;

_t0 := Runtime();
s11 := CountAllConjugacyClassesFast(11);
_e := (Runtime() - _t0) / 1000.0;
Print("\nS_11 total = ", s11, " (expected 3094) in ", _e, "s\n");

if s11 = 3094 then
  Print("=== M6+M7 S_11 PASS ===\n");
else
  Print("=== M6+M7 S_11 FAIL: got ", s11, " expected 3094 ===\n");
fi;

LogTo();
QUIT;
