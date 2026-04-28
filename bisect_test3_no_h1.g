
LogTo("C:/Users/jeffr/Downloads/Lifting/bisect_test3_no_h1.log");
Print("=== Test: test3_no_h1 ===\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
USE_H1_COMPLEMENTS := false;
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
count := CountAllConjugacyClassesFast(6);
Print("S_6 = ", count, " (", (Runtime()-t)/1000.0, "s)\n");
if count = 56 then Print("PASS\n"); else Print("FAIL (expected 56)\n"); fi;

LogTo();
QUIT;
