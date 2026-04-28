
LogTo("C:/Users/jeffr/Downloads/Lifting/test_output_nohom.txt");
Print("S2-S10 Test (USE_GENERAL_AUT_HOM := false)\n");
Print("==============================================\n\n");

# Disable the new path BEFORE reading code that defines it.
USE_GENERAL_AUT_HOM := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

for n in [2..10] do
    Print("\nTesting S_", n, " (expected: ", known[n], ")\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    if result = known[n] then
        Print("Status: PASS (", elapsed, "s)\n");
    else
        Print("Status: FAIL: got ", result, " expected ", known[n], " (", elapsed, "s)\n");
    fi;
od;

LogTo();
QUIT;
