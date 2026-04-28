
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s4.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force fresh recomputation for S_4; pre-fill inherited so cross-checks work.
if IsBound(LIFT_CACHE.("4")) then Unbind(LIFT_CACHE.("4")); fi;
LIFT_CACHE.("3") := 4;

partitions := [[4],[2,2]];
total_fpf := 0;

for part in partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/4/[", _partStr, "]");
    Print("\n>> [", _partStr, "] -> ", COMBO_OUTPUT_DIR, "\n");
    fpf := FindFPFClassesForPartition(4, part);
    Print(">> [", _partStr, "] => ", Length(fpf), " FPF classes\n");
    total_fpf := total_fpf + Length(fpf);
od;

total := 4 + total_fpf;
LIFT_CACHE.("4") := total;

Print("\n=========================================================\n");
Print("S_4 TOTAL: ", total, " (inherited 4 + FPF ", total_fpf, ")\n");
Print("=========================================================\n");
Print("RESULT_TOTAL=", total, "\n");
LogTo();
QUIT;
