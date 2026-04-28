
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== Testing [4,3,2,2] partition of S11 in isolation ===\n\n");

n := 11;
partition := [4, 3, 2, 2];

Print("Calling FindFPFClassesForPartition(11, [4,3,2,2])...\n");
startTime := Runtime();
result := FindFPFClassesForPartition(n, partition);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\nPartition [4,3,2,2] count: ", Length(result), "\n");
Print("Expected: 195\n");
if Length(result) = 195 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL (off by ", 195 - Length(result), ")\n");
fi;
Print("Time: ", elapsed, "s\n");

Print("\n=== H^1 Timing Stats ===\n");
PrintH1TimingStats();

QUIT;
