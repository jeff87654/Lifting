
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

known := [1, 2, 4, 11, 19, 56, 96, 296];
allPass := true;

for n in [2..8] do
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    if result = known[n] then
        Print("S_", n, ": PASS (", result, ") in ", elapsed, "s\n");
    else
        Print("S_", n, ": FAIL (got ", result, ", expected ", known[n], ") in ", elapsed, "s\n");
        allPass := false;
    fi;
od;

Print("\n");
if allPass then
    Print("ALL TESTS PASSED\n");
else
    Print("SOME TESTS FAILED\n");
fi;

QUIT;
