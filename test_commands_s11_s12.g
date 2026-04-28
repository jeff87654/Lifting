
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s11_s12_output.txt");
Print("S11-S12 Test Run\n");
Print("=================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n\nTesting S11 and S12:\n");
Print("========================\n\n");

# Known values from OEIS A005432
known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593, 3094, 10723];

for n in [11, 12] do
    Print("\n========================================\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\n");
    Print("========================================\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\nS_", n, " Result: ", result, "\n");
    Print("Expected: ", known[n], "\n");
    if result = known[n] then
        Print("Status: PASS\n");
    else
        Print("Status: FAIL\n");
    fi;
    Print("Time: ", elapsed, " seconds\n");
od;

Print("\n\n========================================\n");
Print("Test Complete\n");
Print("========================================\n");
LogTo();
QUIT;
