
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s10.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_10; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("10")) then Unbind(LIFT_CACHE.("10")); fi;
LIFT_CACHE.("9") := 554;

partitions := [[10],[8,2],[7,3],[6,4],[6,2,2],[5,5],[5,3,2],[4,4,2],[4,3,3],[4,2,2,2],[3,3,2,2],[2,2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/10/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(10, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 554 + total_fpf;
LIFT_CACHE.("10") := total;

Print("\n=========================================================\n");
Print("S_10 TOTAL: ", total, " (inherited 554 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
