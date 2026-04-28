
USE_TF_DATABASE := false;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_663_tf_off.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn_debug/15/[6,6,3]";
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\n");
t0 := Runtime();
fpf := FindFPFClassesForPartition(15, [6,6,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\n[6,6,3] FPF classes: ", Length(fpf), "\n");
Print("Expected (TF off, per CLAUDE.md): 3248\n");
Print("Elapsed: ", elapsed, "s\n");
LogTo();
QUIT;
