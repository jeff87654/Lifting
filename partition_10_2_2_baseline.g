LogTo("C:/Users/jeffr/Downloads/Lifting/partition_10_2_2_baseline.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
startMs := Runtime(); res := FindFPFClassesForPartition(14, [10,2,2]); Print("RESULT_COUNT=", Length(res), "\n"); Print("ELAPSED_MS=", Runtime()-startMs, "\n");
LogTo();
QUIT;
