
LogTo("C:/Users/jeffr/Downloads/Lifting/s11_verify.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S10 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear runtime caches but keep lift cache
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t := Runtime();
count := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t) / 1000.0;

Print("\n==========================================\n");
Print("S_11 = ", count, " (", elapsed, "s)\n");
if count = 3094 then
    Print("PASS\n");
else
    Print("FAIL (expected 3094)\n");
fi;

LogTo();
QUIT;
