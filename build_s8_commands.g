
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s8.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_8; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("8")) then Unbind(LIFT_CACHE.("8")); fi;
LIFT_CACHE.("7") := 96;

partitions := [[8],[6,2],[5,3],[4,4],[4,2,2],[3,3,2],[2,2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/8/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(8, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 96 + total_fpf;
LIFT_CACHE.("8") := total;

Print("\n=========================================================\n");
Print("S_8 TOTAL: ", total, " (inherited 96 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
