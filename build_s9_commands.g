
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s9.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_9; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("9")) then Unbind(LIFT_CACHE.("9")); fi;
LIFT_CACHE.("8") := 296;

partitions := [[9],[7,2],[6,3],[5,4],[5,2,2],[4,3,2],[3,3,3],[3,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/9/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(9, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 296 + total_fpf;
LIFT_CACHE.("9") := total;

Print("\n=========================================================\n");
Print("S_9 TOTAL: ", total, " (inherited 296 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
