
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s11_s12_clean_output.txt");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# CLEAR stale cache from database (was computed with old buggy code)
FPF_SUBDIRECT_CACHE := rec();

Print("\n=== S11-S12 Clean Test (cache cleared) ===\n\n");

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
        Print("Status: FAIL (off by ", known[n] - result, ")\n");
    fi;
    Print("Time: ", elapsed, " seconds\n");
od;

Print("\n========================================\n");
Print("Test Complete\n");
Print("========================================\n");
LogTo();
QUIT;
