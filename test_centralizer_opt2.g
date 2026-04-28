LogTo("C:/Users/jeffr/Downloads/Lifting/test_centralizer_opt2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

# Test S11 (has [8,3], [7,4] etc partitions with non-abelian factors)
Print("Computing S11...\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - startTime) / 1000.0;
Print("S11 = ", result, " (expected 3094), time = ", elapsed, "s\n");
if result = 3094 then Print("S11 PASS\n"); else Print("S11 FAIL!\n"); fi;

# Test S12 (has [8,4], [6,6] etc)
Print("Computing S12...\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(12);
elapsed := (Runtime() - startTime) / 1000.0;
Print("S12 = ", result, " (expected 10723), time = ", elapsed, "s\n");
if result = 10723 then Print("S12 PASS\n"); else Print("S12 FAIL!\n"); fi;

LogTo();
QUIT;
