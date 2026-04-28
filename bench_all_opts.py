"""Benchmark key S13 partitions with all optimizations (Strategy 1.7 + fingerprint caching).
Each partition gets a fresh H1 cache to measure real improvement."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

log_file = "C:/Users/jeffr/Downloads/Lifting/bench_all_opts.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("=== All Optimizations: Strategy 1.7 + Fingerprint Cache ===\\n\\n");

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

    Print("--- ", part, " of S13 ---\\n");
    t0 := Runtime();
    result := FindFPFClassesForPartition(13, part);
    elapsed := (Runtime() - t0) / 1000.0;
    Print(part, ": ", Length(result), " classes in ", elapsed, "s\\n");
    Print("  orbital: t_module=", H1_ORBITAL_STATS.t_module, "ms t_h1=",
          H1_ORBITAL_STATS.t_h1, "ms t_action=", H1_ORBITAL_STATS.t_action,
          "ms calls=", H1_ORBITAL_STATS.calls, "\\n");
    if IsBound(H1_TIMING_STATS) then
        Print("  H1: calls=", H1_TIMING_STATS.h1_calls, " hits=",
              H1_TIMING_STATS.cache_hits, " fallbacks=",
              H1_TIMING_STATS.fallback_calls, "\\n");
    fi;
    Print("\\n");
od;

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "bench_all_opts.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_all_opts.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running all-opts benchmark for key S13 partitions...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=3600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "bench_all_opts.log"), "r") as f:
    log = f.read()

for line in log.split('\n'):
    if any(x in line for x in ['classes in', '===', '---', 'orbital:', 'H1:']):
        print(line.strip())

warning_count = log.count('invalid')
if warning_count > 0:
    print(f"\nWARNING: {warning_count} 'invalid' mentions in log")

if stderr and 'Syntax warning' not in stderr[:200]:
    print(f"stderr: {stderr[:500]}")
