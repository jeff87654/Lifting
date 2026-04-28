
LogTo("C:/Users/jeffr/Downloads/Lifting/full_verify.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

known := rec();
known.2 := 2; known.3 := 4; known.4 := 11; known.5 := 19;
known.6 := 56; known.7 := 96; known.8 := 296;
known.9 := 554; known.10 := 1593;
known.11 := 3094;

allPass := true;
totalStart := Runtime();

for n in [2..10] do
    t := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t) / 1000.0;
    expected := known.(n);
    if count = expected then
        Print("S_", n, " = ", count, " PASS (", elapsed, "s)\n");
    else
        Print("S_", n, " = ", count, " FAIL (expected ", expected, ") (", elapsed, "s)\n");
        allPass := false;
    fi;
od;

totalTime := (Runtime() - totalStart) / 1000.0;
Print("\n==========================================\n");
if allPass then
    Print("ALL PASS in ", totalTime, "s\n");
else
    Print("SOME FAILURES in ", totalTime, "s\n");
fi;

LogTo();
QUIT;
