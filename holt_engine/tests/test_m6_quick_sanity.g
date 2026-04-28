LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_m6_quick_sanity.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\n");

# Quick sanity: S2..S10 total should be 1593 (OEIS A000638).
_t0 := Runtime();
total := CountAllConjugacyClassesFast(10);
_elapsed := (Runtime() - _t0) / 1000.0;
Print("\nS2..S10 total = ", total, " (expected 1593) in ", _elapsed, "s\n");

if total = 1593 then
  Print("=== M6 sanity PASS ===\n");
else
  Print("=== M6 sanity FAIL: got ", total, " expected 1593 ===\n");
fi;

LogTo();
QUIT;
