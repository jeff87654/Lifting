
LogTo("C:/Users/jeffr/Downloads/Lifting/bench_all_opts.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("=== All Optimizations: Strategy 1.7 + Fingerprint Cache ===\n\n");

partitions := [ [6,4,3], [5,4,4], [10,3], [8,5], [8,3,2], [4,4,3,2] ];

for part in partitions do
    # Fresh caches per partition for accurate timing
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    H1_ORBITAL_STATS := rec(
        calls := 0, total_orbits := 0, total_points := 0,
        orbit_time := 0, skipped_trivial := 0,
        t_module := 0, t_h1 := 0, t_action := 0, t_orbits := 0, t_convert := 0
    );
    if IsBound(H1_TIMING_STATS) then
        H1_TIMING_STATS.h1_calls := 0;
        H1_TIMING_STATS.cache_hits := 0;
        H1_TIMING_STATS.coprime_skips := 0;
        H1_TIMING_STATS.fallback_calls := 0;
        H1_TIMING_STATS.h1_time := 0;
    fi;

    Print("--- ", part, " of S13 ---\n");
    t0 := Runtime();
    result := FindFPFClassesForPartition(13, part);
    elapsed := (Runtime() - t0) / 1000.0;
    Print(part, ": ", Length(result), " classes in ", elapsed, "s\n");
    Print("  orbital: t_module=", H1_ORBITAL_STATS.t_module, "ms t_h1=",
          H1_ORBITAL_STATS.t_h1, "ms t_action=", H1_ORBITAL_STATS.t_action,
          "ms calls=", H1_ORBITAL_STATS.calls, "\n");
    if IsBound(H1_TIMING_STATS) then
        Print("  H1: calls=", H1_TIMING_STATS.h1_calls, " hits=",
              H1_TIMING_STATS.cache_hits, " fallbacks=",
              H1_TIMING_STATS.fallback_calls, "\n");
    fi;
    Print("\n");
od;

LogTo();
QUIT;
