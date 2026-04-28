
USE_TF_DATABASE := true;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_655_v3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[6,5,5]";
fpf := FindFPFClassesForPartition(16, [6,5,5]);
Print("RESULT [6,5,5] = ", Length(fpf), " (expected 1283)
");
Print("TF stats: ", TF_LOOKUP_STATS, "
");
LogTo();
QUIT;
