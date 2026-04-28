LogTo("C:/Users/jeffr/Downloads/Lifting/test_552.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
startTime := Runtime();
r := FindFPFClassesForPartition(12, [5,5,2]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("[5,5,2] = ", Length(r), ", time = ", elapsed, "s\n");
if Length(r) = 62 then
  Print("PASS: got 62, expected 62\n");
else
  Print("FAIL: got ", Length(r), ", expected 62\n");
fi;
LogTo();
QUIT;
