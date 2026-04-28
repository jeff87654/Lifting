
LogTo("C:/Users/jeffr/Downloads/Lifting/test_smallgroup.log");
Print("Testing S2-S10 with small-group AllSubgroups fast path\n");
Print("Start time: ", StringTime(Runtime()), "\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Run S2-S10
for n in [2..10] do
    t := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t) / 1000.0;
    Print("S", n, " = ", count, " (", elapsed, "s)\n");
od;

Print("\nExpected: S10 = 1593\n");
Print("Done at ", StringTime(Runtime()), "\n");
LogTo();
QUIT;
