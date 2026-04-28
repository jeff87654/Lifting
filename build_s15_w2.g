
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s15_w2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
my_partitions := [[8,5,2],[6,6,3],[8,3,2,2],[11,4],[5,5,5],[7,4,2,2],[5,4,2,2,2],[5,3,3,2,2],[5,2,2,2,2,2],[3,2,2,2,2,2,2]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/15/[", _partStr, "]");
    Print("\n[w2] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(15, part);
    Print("[w2] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w2] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
