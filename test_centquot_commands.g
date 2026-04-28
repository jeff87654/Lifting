
LogTo("C:/Users/jeffr/Downloads/Lifting/test_centquot_output.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Testing S2-S10 with centralizer quotient optimization ===\n");
t0 := Runtime();

expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

allPass := true;
for n in [2..10] do
    t1 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := Runtime() - t1;
    if count = expected[n-1] then
        Print("S", n, " = ", count, " PASS (", elapsed, "ms)\n");
    else
        Print("S", n, " = ", count, " FAIL (expected ", expected[n-1], ") (", elapsed, "ms)\n");
        allPass := false;
    fi;
od;

total := Runtime() - t0;
Print("\nTotal time: ", total, "ms\n");
if allPass then
    Print("ALL PASS\n");
else
    Print("SOME TESTS FAILED\n");
fi;

LogTo();
QUIT;
