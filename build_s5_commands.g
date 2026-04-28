
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s5.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_5; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("5")) then Unbind(LIFT_CACHE.("5")); fi;
LIFT_CACHE.("4") := 11;

partitions := [[5],[3,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/5/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(5, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 11 + total_fpf;
LIFT_CACHE.("5") := total;

Print("\n=========================================================\n");
Print("S_5 TOTAL: ", total, " (inherited 11 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
