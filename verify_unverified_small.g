LogTo("C:/Users/jeffr/Downloads/Lifting/verify_unverified_small.log");

# Rerun small unverified partitions to check totals against disk.
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Use scratch dir so we don't disturb disk files
scratch_dir := "C:/Users/jeffr/Downloads/Lifting/verify_scratch_partitions";
Exec(Concatenation("mkdir -p \"", scratch_dir, "\""));

partitions_to_check := [
    [[3,3,3,3,3,3], 429],
    [[2,2,2,2,2,2,2,2,2], 506],
    [[3,3,3,3,2,2,2], 1372]
];

for entry in partitions_to_check do
    part := entry[1];
    disk_sum := entry[2];
    pname := Concatenation("[", JoinStringsWithSeparator(List(part, String), ","), "]");
    Print("\n========================\n");
    Print("Partition ", part, " (disk sum: ", disk_sum, ")\n");
    Print("========================\n");

    # Use scratch combo dir so iteration writes there (not on real disk)
    COMBO_OUTPUT_DIR := Concatenation(scratch_dir, "/", pname);
    Exec(Concatenation("mkdir -p \"", COMBO_OUTPUT_DIR, "\""));
    Exec(Concatenation("rm -f \"", COMBO_OUTPUT_DIR, "\"/*.g"));
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    t0 := Runtime();
    fpf := FindFPFClassesForPartition(18, part);
    t := (Runtime() - t0)/1000.0;
    Print("=> ", Length(fpf), " classes (", t, "s)\n");
    Print("DELTA vs disk: ", Length(fpf) - disk_sum, "\n");
od;

LogTo();
QUIT;
