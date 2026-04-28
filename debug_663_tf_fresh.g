
USE_TF_DATABASE := true;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_663_tf_fresh.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
# Ensure TF cache starts empty
TF_SUBGROUP_LATTICE := rec();
TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn_debug/15_tf_fresh/[6,6,3]";
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\n");
Print("TF_SUBGROUP_LATTICE initial entries: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\n");
t0 := Runtime();
fpf := FindFPFClassesForPartition(15, [6,6,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\n[6,6,3] FPF classes: ", Length(fpf), "\n");
Print("TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\n");
Print("Elapsed: ", elapsed, "s\n");
LogTo();
QUIT;
