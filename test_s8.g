# Quick test for S8
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s8_output.txt");
Print("Testing S8 (baseline, C2 opt disabled)\n");
Print("========================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\nTesting S8 (expected: 296):\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n\nFinal S8 Result: ", result, "\n");
Print("Expected: 296\n");
if result = 296 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL (off by ", 296 - result, ")\n");
fi;
Print("Time: ", elapsed, " seconds\n");

LogTo();
QUIT;
