
LogTo("C:/Users/jeffr/Downloads/Lifting/bench_orbital_profile.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("Profiling H^1 orbital path for [6,4,3] of S13...\n");
t0 := Runtime();
result := FindFPFClassesForPartition(13, [6,4,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[6,4,3]: ", Length(result), " classes in ", elapsed, "s\n");

# Print orbital profiling stats
Print("\n=== H^1 Orbital Profiling ===\n");
Print("  calls:     ", H1_ORBITAL_STATS.calls, "\n");
Print("  t_module:  ", H1_ORBITAL_STATS.t_module, "ms (ChiefFactorAsModule incl CCR)\n");
Print("  t_h1:      ", H1_ORBITAL_STATS.t_h1, "ms (CachedComputeH1)\n");
Print("  t_action:  ", H1_ORBITAL_STATS.t_action, "ms (BuildH1ActionRecord)\n");
Print("  t_orbits:  ", H1_ORBITAL_STATS.t_orbits, "ms (ComputeH1Orbits)\n");
Print("  t_convert: ", H1_ORBITAL_STATS.t_convert, "ms (CocycleToComplement)\n");
Print("  orbit_time:", H1_ORBITAL_STATS.orbit_time, "ms (total in GetH1OrbitReps)\n");
Print("  total_orbits: ", H1_ORBITAL_STATS.total_orbits, "\n");
Print("  total_points: ", H1_ORBITAL_STATS.total_points, "\n");
Print("  skipped_trivial: ", H1_ORBITAL_STATS.skipped_trivial, "\n");

# Print H1 timing stats
Print("\n=== H^1 Global Stats ===\n");
Print("  h1_calls: ", H1_TIMING_STATS.h1_calls, "\n");
Print("  coprime_skips: ", H1_TIMING_STATS.coprime_skips, "\n");
Print("  fallback_calls: ", H1_TIMING_STATS.fallback_calls, "\n");
Print("  h1_time: ", H1_TIMING_STATS.h1_time, "ms\n");

LogTo();
QUIT;
