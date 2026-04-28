
LogTo("C:/Users/jeffr/Downloads/Lifting/test_output.txt");
Print("S14 Optimization Test Run\n");
Print("==========================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n\nTesting S2 through S10:\n");
Print("========================\n\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

for n in [2..10] do
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
