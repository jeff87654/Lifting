
LogTo("C:/Users/jeffr/Downloads/Lifting/bisect_test1_current.log");
Print("=== Test: test1_current ===\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
count := CountAllConjugacyClassesFast(6);
Print("S_6 = ", count, " (", (Runtime()-t)/1000.0, "s)\n");
if count = 56 then Print("PASS\n"); else Print("FAIL (expected 56)\n"); fi;

LogTo();
QUIT;
