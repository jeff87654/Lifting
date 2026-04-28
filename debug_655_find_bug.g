
USE_TF_DATABASE := true;;
DIAG_TF_VERIFY := true;;
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_655_find_bug.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_sn_debug/16_find_bug/[6,5,5]";
fpf := FindFPFClassesForPartition(16, [6,5,5]);
Print("\n[6,5,5] FPF classes: ", Length(fpf), "\n");
if IsBound(DIAG_TF_MISMATCHES) then
    Print("Mismatches: ", Length(DIAG_TF_MISMATCHES), "\n");
    for i in [1..Minimum(10, Length(DIAG_TF_MISMATCHES))] do
        rec := DIAG_TF_MISMATCHES[i];
        Print("  #", i, ": |Q|=", rec.Q_size, " |M_bar|=", rec.M_bar_size,
              " |R|=", rec.R_size, " |TF|=", rec.TF_size,
              " TFtop=", rec.tftop_count, " NSCR=", rec.nscr_count, "\n");
    od;
fi;
LogTo();
QUIT;
