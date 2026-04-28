
LogTo("C:/Users/jeffr/Downloads/Lifting/s11_benchmark.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S10 from cache, but clear S11 to force recomputation
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Unbind(LIFT_CACHE.("11"));

# Clear H^1 and FPF caches
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

t := Runtime();
count := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t) / 1000.0;

if count = 3094 then
    Print("S_11 = ", count, " PASS (", elapsed, "s)\n");
else
    Print("S_11 = ", count, " FAIL (expected 3094) (", elapsed, "s)\n");
fi;

LogTo();
QUIT;
