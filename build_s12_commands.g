
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s12.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_12; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("12")) then Unbind(LIFT_CACHE.("12")); fi;
LIFT_CACHE.("11") := 3094;

partitions := [[12],[10,2],[9,3],[8,4],[8,2,2],[7,5],[7,3,2],[6,6],[6,4,2],[6,3,3],[6,2,2,2],[5,5,2],[5,4,3],[5,3,2,2],[4,4,4],[4,4,2,2],[4,3,3,2],[4,2,2,2,2],[3,3,3,3],[3,3,2,2,2],[2,2,2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/12/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(12, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 3094 + total_fpf;
LIFT_CACHE.("12") := total;

Print("\n=========================================================\n");
Print("S_12 TOTAL: ", total, " (inherited 3094 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
