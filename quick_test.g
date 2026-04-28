# Quick test of optimization
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== Quick S8 Test ===\n");

# Clear caches first
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();

startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n=== SUMMARY ===\n");
Print("S_8 result: ", result, " (expected: 296)\n");
Print("Total time: ", elapsed, " seconds\n");

if result = 296 then
    Print("STATUS: PASS\n");
else
    Print("STATUS: FAIL\n");
fi;

QUIT;
