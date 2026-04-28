
USE_TF_DATABASE := false;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_655_tf_off.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn_debug/16_tf_off/[6,5,5]";
t0 := Runtime();
fpf := FindFPFClassesForPartition(16, [6,5,5]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\n[6,5,5] FPF classes: ", Length(fpf), "\n");
Print("Elapsed: ", elapsed, "s\n");
LogTo();
QUIT;
