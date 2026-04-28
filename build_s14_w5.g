
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s14_w5.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("13") := 20832;
my_partitions := [[9,3,2],[6,4,4],[6,6,2],[10,2,2],[5,4,3,2],[6,4,2,2],[5,3,3,3],[4,4,2,2,2],[3,3,3,3,2]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/14/[", _partStr, "]");
    Print("\n[w5] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(14, part);
    Print("[w5] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w5] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
