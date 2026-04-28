
LogTo("C:/Users/jeffr/Downloads/Lifting/bench_s13_slow.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache (skip recomputation)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF and H^1 caches (want fresh computation for partition)
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Benchmark [6,4,3] - was 340s before all optimizations
Print("Benchmarking [6,4,3] of S13...\n");
t0 := Runtime();
result := FindFPFClassesForPartition(13, [6,4,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[6,4,3]: ", Length(result), " classes in ", elapsed, "s\n");

# Also try [5,4,4] - was 425s
Print("\nBenchmarking [5,4,4] of S13...\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result := FindFPFClassesForPartition(13, [5,4,4]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[5,4,4]: ", Length(result), " classes in ", elapsed, "s\n");

# Stats
if IsBound(H1_TIMING_STATS) then
    Print("H^1 calls: ", H1_TIMING_STATS.h1_calls, "\n");
    Print("Coprime skips: ", H1_TIMING_STATS.coprime_skips, "\n");
fi;

LogTo();
QUIT;
