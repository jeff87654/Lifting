LogTo("C:/Users/jeffr/Downloads/Lifting/test_centralizer_opt3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

Print("Testing [8,4] of S12...\n");
startTime := Runtime();
r := FindFPFClassesForPartition(12, [8,4]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("  [8,4] = ", Length(r), " classes (expected 1260), time = ", elapsed, "s\n");
if Length(r) = 1260 then Print("  PASS\n"); else Print("  FAIL!\n"); fi;

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

Print("Testing [6,6] of S12...\n");
startTime := Runtime();
r := FindFPFClassesForPartition(12, [6,6]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("  [6,6] = ", Length(r), " classes (expected 473), time = ", elapsed, "s\n");
if Length(r) = 473 then Print("  PASS\n"); else Print("  FAIL!\n"); fi;

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

Print("Testing [6,4,2] of S12...\n");
startTime := Runtime();
r := FindFPFClassesForPartition(12, [6,4,2]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("  [6,4,2] = ", Length(r), " classes (expected 2547), time = ", elapsed, "s\n");
if Length(r) = 2547 then Print("  PASS\n"); else Print("  FAIL!\n"); fi;

LogTo();
QUIT;
