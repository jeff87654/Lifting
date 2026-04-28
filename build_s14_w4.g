
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s14_w4.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("13") := 20832;
my_partitions := [[10,4],[9,5],[6,5,3],[8,2,2,2],[7,5,2],[4,4,4,2],[7,3,2,2],[6,2,2,2,2],[4,3,3,2,2],[4,2,2,2,2,2],[14]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/14/[", _partStr, "]");
    Print("\n[w4] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(14, part);
    Print("[w4] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w4] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
