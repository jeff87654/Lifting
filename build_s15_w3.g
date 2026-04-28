
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s15_w3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
my_partitions := [[9,4,2],[8,7],[7,6,2],[7,5,3],[5,4,3,3],[5,5,3,2],[4,3,3,3,2],[6,3,2,2,2],[7,2,2,2,2],[3,3,3,2,2,2]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/15/[", _partStr, "]");
    Print("\n[w3] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(15, part);
    Print("[w3] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w3] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
