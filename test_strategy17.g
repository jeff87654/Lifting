
LogTo("C:/Users/jeffr/Downloads/Lifting/test_strategy17.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;
t_total := Runtime();

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

Print("\nTotal CPU: ", (Runtime() - t_total) / 1000.0, "s\n");

# Print H1 cache stats
Print("\nH1 cache entries: ", Length(RecNames(H1_CACHE)), "\n");
if IsBound(H1_TIMING_STATS) then
    Print("H1 calls: ", H1_TIMING_STATS.h1_calls, "\n");
    Print("Cache hits: ", H1_TIMING_STATS.cache_hits, "\n");
    Print("Fallback calls: ", H1_TIMING_STATS.fallback_calls, "\n");
    Print("H1 time: ", H1_TIMING_STATS.h1_time, "ms\n");
fi;

if allPass then
    Print("\nALL PASS (strategy 1.7)\n");
else
    Print("\nSOME FAILED\n");
fi;

LogTo();
QUIT;
