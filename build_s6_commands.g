
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s6.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_6; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("6")) then Unbind(LIFT_CACHE.("6")); fi;
LIFT_CACHE.("5") := 19;

partitions := [[6],[4,2],[3,3],[2,2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/6/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(6, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 19 + total_fpf;
LIFT_CACHE.("6") := total;

Print("\n=========================================================\n");
Print("S_6 TOTAL: ", total, " (inherited 19 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
