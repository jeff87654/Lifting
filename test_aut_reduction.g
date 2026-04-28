LogTo("C:/Users/jeffr/Downloads/Lifting/test_aut_reduction.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Test 1: S12 partitions with A_6 chief factor
# These have |M/N| = 360 (A_6) layers
Print("=== Test: S12 partitions with A_6 layers ===\n");

# [6,6] has A_6 chief factor
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r := FindFPFClassesForPartition(12, [6,6]);
Print("[6,6] = ", Length(r), " (expected 473) ", (Runtime()-t0)/1000.0, "s\n");
if Length(r) <> 473 then Print("FAIL!\n"); fi;

# [6,4,2] has A_6 chief factor
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r := FindFPFClassesForPartition(12, [6,4,2]);
Print("[6,4,2] = ", Length(r), " (expected 1126) ", (Runtime()-t0)/1000.0, "s\n");
if Length(r) <> 1126 then Print("FAIL!\n"); fi;

# [6,3,3] has A_6 chief factor
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r := FindFPFClassesForPartition(12, [6,3,3]);
Print("[6,3,3] = ", Length(r), " (expected 269) ", (Runtime()-t0)/1000.0, "s\n");
if Length(r) <> 269 then Print("FAIL!\n"); fi;

# [6,2,2,2] has A_6 chief factor
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r := FindFPFClassesForPartition(12, [6,2,2,2]);
Print("[6,2,2,2] = ", Length(r), " (expected 285) ", (Runtime()-t0)/1000.0, "s\n");
if Length(r) <> 285 then Print("FAIL!\n"); fi;

Print("\n=== Test: S10 full (sanity check) ===\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
n := CountAllConjugacyClassesFast(10);
Print("S10 = ", n, " (expected 1593) ", (Runtime()-t0)/1000.0, "s\n");
if n <> 1593 then Print("FAIL!\n"); fi;

LogTo();
QUIT;
