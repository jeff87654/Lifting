LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_m6_m7_s11_s13.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\n");

# Force recomputation of S11, S12, S13.
if IsBound(LIFT_CACHE.("11")) then Unbind(LIFT_CACHE.("11")); fi;
if IsBound(LIFT_CACHE.("12")) then Unbind(LIFT_CACHE.("12")); fi;
if IsBound(LIFT_CACHE.("13")) then Unbind(LIFT_CACHE.("13")); fi;
# Clear FPF cache so timings are fresh.
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t_s11 := Runtime();
s11 := CountAllConjugacyClassesFast(11);
_elapsed_s11 := (Runtime() - _t_s11) / 1000.0;
Print("\n=== S11 = ", s11, " (expected 3094) in ", _elapsed_s11, "s ===\n");

_t_s12 := Runtime();
s12 := CountAllConjugacyClassesFast(12);
_elapsed_s12 := (Runtime() - _t_s12) / 1000.0;
Print("\n=== S12 = ", s12, " (expected 10723) in ", _elapsed_s12, "s ===\n");

_t_s13 := Runtime();
s13 := CountAllConjugacyClassesFast(13);
_elapsed_s13 := (Runtime() - _t_s13) / 1000.0;
Print("\n=== S13 = ", s13, " (expected 20832) in ", _elapsed_s13, "s ===\n");

Print("\n=== SUMMARY ===\n");
Print("S11: ", s11, " (expected 3094), ", _elapsed_s11, "s\n");
Print("S12: ", s12, " (expected 10723), ", _elapsed_s12, "s\n");
Print("S13: ", s13, " (expected 20832), ", _elapsed_s13, "s\n");
if s11 = 3094 and s12 = 10723 and s13 = 20832 then
  Print("=== M6+M7 S11..S13 PASS ===\n");
else
  Print("=== M6+M7 S11..S13 FAIL ===\n");
fi;

LogTo();
QUIT;
