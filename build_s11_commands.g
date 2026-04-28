
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s11.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_11; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("11")) then Unbind(LIFT_CACHE.("11")); fi;
LIFT_CACHE.("10") := 1593;

partitions := [[11],[9,2],[8,3],[7,4],[7,2,2],[6,5],[6,3,2],[5,4,2],[5,3,3],[5,2,2,2],[4,4,3],[4,3,2,2],[3,3,3,2],[3,2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/11/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(11, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 1593 + total_fpf;
LIFT_CACHE.("11") := total;

Print("\n=========================================================\n");
Print("S_11 TOTAL: ", total, " (inherited 1593 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
