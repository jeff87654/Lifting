LogTo("C:/Users/jeffr/Downloads/Lifting/test_s12_all.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Ground truth from brute force (s12_partition_classes_output.txt)
# Verified against C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s12_partition_classes_output.txt
# FPF total = 7629 = 10723 (S12) - 3094 (S11)
expected := rec();
expected.("12") := 301;
expected.("10_2") := 116;
expected.("9_3") := 143;
expected.("8_4") := 1376;
expected.("8_2_2") := 578;
expected.("7_5") := 44;
expected.("7_3_2") := 39;
expected.("6_6") := 473;
expected.("6_4_2") := 1126;
expected.("6_3_3") := 269;
expected.("6_2_2_2") := 285;
expected.("5_5_2") := 62;
expected.("5_4_3") := 205;
expected.("5_3_2_2") := 86;
expected.("4_4_4") := 894;
expected.("4_4_2_2") := 932;
expected.("4_3_3_2") := 277;
expected.("4_2_2_2_2") := 263;
expected.("3_3_3_3") := 50;
expected.("3_3_2_2_2") := 74;
expected.("2_2_2_2_2_2") := 36;

partitions := [
    [12], [10,2], [9,3], [8,4], [8,2,2], [7,5], [7,3,2],
    [6,6], [6,4,2], [6,3,3], [6,2,2,2],
    [5,5,2], [5,4,3], [5,3,2,2],
    [4,4,4], [4,4,2,2], [4,3,3,2], [4,2,2,2,2],
    [3,3,3,3], [3,3,2,2,2], [2,2,2,2,2,2]
];

fails := 0;
for part in partitions do
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
    FPF_SUBDIRECT_CACHE := rec();
    t0 := Runtime();
    r := FindFPFClassesForPartition(12, part);
    t := (Runtime() - t0) / 1000.0;
    key := JoinStringsWithSeparator(List(part, String), "_");
    exp := expected.(key);
    if Length(r) = exp then
        Print(part, " = ", Length(r), " PASS (", t, "s)\n");
    else
        Print(part, " = ", Length(r), " FAIL! expected ", exp, " (", t, "s)\n");
        fails := fails + 1;
    fi;
od;

Print("\n", fails, " failures out of ", Length(partitions), " partitions\n");
expTotal := Sum(RecNames(expected), k -> expected.(k));
Print("Expected FPF total: ", expTotal, "\n");

LogTo();
QUIT;
