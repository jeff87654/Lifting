
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s15_w0.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("14") := 75154;
my_partitions := [[12,3]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/15/[", _partStr, "]");
    Print("\n[w0] >> ", part, "\n");
    fpf := FindFPFClassesForPartition(15, part);
    Print("[w0] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    total_fpf := total_fpf + Length(fpf);
od;
Print("\n[w0] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
