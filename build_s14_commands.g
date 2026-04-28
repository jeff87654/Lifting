
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s14.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_14; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("14")) then Unbind(LIFT_CACHE.("14")); fi;
LIFT_CACHE.("13") := 20832;

partitions := [[14],[12,2],[11,3],[10,4],[10,2,2],[9,5],[9,3,2],[8,6],[8,4,2],[8,3,3],[8,2,2,2],[7,7],[7,5,2],[7,4,3],[7,3,2,2],[6,6,2],[6,5,3],[6,4,4],[6,4,2,2],[6,3,3,2],[6,2,2,2,2],[5,5,4],[5,5,2,2],[5,4,3,2],[5,3,3,3],[5,3,2,2,2],[4,4,4,2],[4,4,3,3],[4,4,2,2,2],[4,3,3,2,2],[4,2,2,2,2,2],[3,3,3,3,2],[3,3,2,2,2,2],[2,2,2,2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/14/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(14, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 20832 + total_fpf;
LIFT_CACHE.("14") := total;

Print("\n=========================================================\n");
Print("S_14 TOTAL: ", total, " (inherited 20832 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
