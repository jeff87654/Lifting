
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s7.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_7; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("7")) then Unbind(LIFT_CACHE.("7")); fi;
LIFT_CACHE.("6") := 56;

partitions := [[7],[5,2],[4,3],[3,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/7/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(7, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 56 + total_fpf;
LIFT_CACHE.("7") := total;

Print("\n=========================================================\n");
Print("S_7 TOTAL: ", total, " (inherited 56 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
