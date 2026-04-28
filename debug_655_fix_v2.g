
USE_TF_DATABASE := true;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_655_fix_v2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[6,5,5]";
fpf := FindFPFClassesForPartition(16, [6,5,5]);
Print("
[6,5,5] with fixed TF-top: ", Length(fpf), "
");
LogTo();
QUIT;
