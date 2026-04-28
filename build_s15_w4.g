
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s15_w4.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
my_partitions := [[9,6],[6,5,4],[6,4,3,2],[6,3,3,3],[4,4,4,3],[13,2],[6,5,2,2],[4,3,2,2,2,2],[15]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/15/[", _partStr, "]");
    Print("\n[w4] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(15, part);
    Print("[w4] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w4] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
