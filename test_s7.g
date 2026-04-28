# Quick test for S7 to verify C2 optimization fix
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s7_output.txt");
Print("Testing S7 C2 optimization fix\n");
Print("================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\nTesting S7 (expected: 96):\n");
Print("===========================\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(7);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n\nFinal S7 Result: ", result, "\n");
Print("Expected: 96\n");
if result = 96 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL (off by ", 96 - result, ")\n");
fi;
Print("Time: ", elapsed, " seconds\n");

LogTo();
QUIT;
