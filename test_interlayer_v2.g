LogTo("C:/Users/jeffr/Downloads/Lifting/test_interlayer_v2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test S10 = 1593
startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := (Runtime() - startTime) / 1000.0;
Print("S10 = ", result, " (expected 1593), time = ", elapsed, "s\n");
if result = 1593 then Print("S10 PASS\n"); else Print("S10 FAIL!\n"); fi;

# Test [6,4,2] of S12 = 1126
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();
startTime := Runtime();
r := FindFPFClassesForPartition(12, [6,4,2]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("[6,4,2] = ", Length(r), " (expected 1126), time = ", elapsed, "s\n");
if Length(r) = 1126 then Print("[6,4,2] PASS\n"); else Print("[6,4,2] FAIL!\n"); fi;

LogTo();
QUIT;
