
LogTo("C:/Users/jeffr/Downloads/Lifting/s12_verify.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S11 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(LIFT_CACHE.12) then Unbind(LIFT_CACHE.12); fi;

# Clear runtime caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t := Runtime();
count := CountAllConjugacyClassesFast(12);
elapsed := (Runtime() - t) / 1000.0;

Print("\n==========================================\n");
Print("S_12 = ", count, " (", elapsed, "s)\n");
if count = 10723 then
    Print("PASS\n");
else
    Print("FAIL (expected 10723)\n");
fi;

LogTo();
QUIT;
