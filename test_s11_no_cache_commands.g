
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s11_no_cache_output.txt");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# CLEAR the stale cache loaded from database
FPF_SUBDIRECT_CACHE := rec();

Print("\n=== Testing S11 with CLEARED cache ===\n\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593, 3094, 10723];

startTime := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\nS_11 Result: ", result, "\n");
Print("Expected: ", known[11], "\n");
if result = known[11] then
    Print("Status: PASS\n");
else
    Print("Status: FAIL (off by ", known[11] - result, ")\n");
fi;
Print("Time: ", elapsed, " seconds\n");

LogTo();
QUIT;
