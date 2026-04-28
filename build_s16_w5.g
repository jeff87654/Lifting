
LogTo("C:/Users/jeffr/Downloads/Lifting/build_s16_w5.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LIFT_CACHE.("15") := 159129;

# Heartbeat file - LiftThroughLayer writes periodic 'alive' lines here,
# and we bracket each partition with 'starting'/'completed' markers
# mirroring parallel_s18/run_s18.py.
_HEARTBEAT_FILE := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/worker_5_heartbeat.txt";
PrintTo(_HEARTBEAT_FILE, "worker 5 starting n=16 partitions=",
    Length([[8,8],[10,6],[9,5,2],[8,4,2,2],[14,2],[7,4,3,2],[10,2,2,2],[6,6,2,2],[6,4,2,2,2],[6,2,2,2,2,2],[5,3,2,2,2,2]]), "\n");

my_partitions := [[8,8],[10,6],[9,5,2],[8,4,2,2],[14,2],[7,4,3,2],[10,2,2,2],[6,6,2,2],[6,4,2,2,2],[6,2,2,2,2,2],[5,3,2,2,2,2]];
total_fpf := 0;
worker_start := Runtime();
for part in my_partitions do
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[", _partStr, "]");
    Print("\n[w5] >> ", part, "\n");
    PrintTo(_HEARTBEAT_FILE, "starting partition ", part, "\n");
    fpf := FindFPFClassesForPartition(16, part);
    Print("[w5] >> ", part, " => ", Length(fpf), " classes (",
          (Runtime() - worker_start) / 1000.0, "s elapsed)\n");
    PrintTo(_HEARTBEAT_FILE, "completed partition ", part, " = ",
            Length(fpf), " classes (",
            Int((Runtime() - worker_start) / 1000), "s worker-total)\n");
    total_fpf := total_fpf + Length(fpf);
od;
PrintTo(_HEARTBEAT_FILE, "worker 5 done total=", total_fpf, "\n");
Print("\n[w5] WORKER_TOTAL=", total_fpf, "\n");
LogTo();
QUIT;
