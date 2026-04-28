
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s13.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_13; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("13")) then Unbind(LIFT_CACHE.("13")); fi;
LIFT_CACHE.("12") := 10723;

partitions := [[13],[11,2],[10,3],[9,4],[9,2,2],[8,5],[8,3,2],[7,6],[7,4,2],[7,3,3],[7,2,2,2],[6,5,2],[6,4,3],[6,3,2,2],[5,5,3],[5,4,4],[5,4,2,2],[5,3,3,2],[5,2,2,2,2],[4,4,3,2],[4,3,3,3],[4,3,2,2,2],[3,3,3,2,2],[3,2,2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/13/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(13, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 10723 + total_fpf;
LIFT_CACHE.("13") := total;

Print("\n=========================================================\n");
Print("S_13 TOTAL: ", total, " (inherited 10723 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
