
LogTo("C:/Users/jeffr/Downloads/Lifting/verify_s2_s10.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;

for n in [1..10] do
    t0 := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t0) / 1000.0;
    if result = expected[n] then
        Print("S", n, " = ", result, " PASS (", elapsed, "s)\n");
    else
        Print("S", n, " = ", result, " FAIL (expected ", expected[n], ")\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\nALL PASS\n");
else
    Print("\nSOME FAILED\n");
fi;

LogTo();
QUIT;
