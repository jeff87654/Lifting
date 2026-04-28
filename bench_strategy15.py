"""Profile [6,4,3] and [5,4,4] with Strategy 1.5 to measure t_module reduction."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

log_file = "C:/Users/jeffr/Downloads/Lifting/bench_strategy15.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Benchmarking with Strategy 1.5 ===\\n\\n");

# Benchmark [6,4,3]
Print("--- [6,4,3] of S13 ---\\n");
H1_ORBITAL_STATS := rec(
    calls := 0, total_orbits := 0, total_points := 0,
    orbit_time := 0, skipped_trivial := 0,
    t_module := 0, t_h1 := 0, t_action := 0, t_orbits := 0, t_convert := 0
);
t0 := Runtime();
result := FindFPFClassesForPartition(13, [6,4,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[6,4,3]: ", Length(result), " classes in ", elapsed, "s\\n");
Print("  t_module:  ", H1_ORBITAL_STATS.t_module, "ms\\n");
Print("  t_h1:      ", H1_ORBITAL_STATS.t_h1, "ms\\n");
Print("  t_action:  ", H1_ORBITAL_STATS.t_action, "ms\\n");
Print("  t_orbits:  ", H1_ORBITAL_STATS.t_orbits, "ms\\n");
Print("  t_convert: ", H1_ORBITAL_STATS.t_convert, "ms\\n");
Print("  calls:     ", H1_ORBITAL_STATS.calls, "\\n");
Print("  total_orbits: ", H1_ORBITAL_STATS.total_orbits, "\\n");
Print("  total_points: ", H1_ORBITAL_STATS.total_points, "\\n\\n");

# Clear caches for second benchmark
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Benchmark [5,4,4]
Print("--- [5,4,4] of S13 ---\\n");
H1_ORBITAL_STATS := rec(
    calls := 0, total_orbits := 0, total_points := 0,
    orbit_time := 0, skipped_trivial := 0,
    t_module := 0, t_h1 := 0, t_action := 0, t_orbits := 0, t_convert := 0
);
t0 := Runtime();
result2 := FindFPFClassesForPartition(13, [5,4,4]);
elapsed2 := (Runtime() - t0) / 1000.0;
Print("[5,4,4]: ", Length(result2), " classes in ", elapsed2, "s\\n");
Print("  t_module:  ", H1_ORBITAL_STATS.t_module, "ms\\n");
Print("  t_h1:      ", H1_ORBITAL_STATS.t_h1, "ms\\n");
Print("  t_action:  ", H1_ORBITAL_STATS.t_action, "ms\\n");
Print("  t_orbits:  ", H1_ORBITAL_STATS.t_orbits, "ms\\n");
Print("  t_convert: ", H1_ORBITAL_STATS.t_convert, "ms\\n");
Print("  calls:     ", H1_ORBITAL_STATS.calls, "\\n");
Print("  total_orbits: ", H1_ORBITAL_STATS.total_orbits, "\\n");
Print("  total_points: ", H1_ORBITAL_STATS.total_points, "\\n\\n");

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "bench_strategy15.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_strategy15.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running Strategy 1.5 profiling benchmark...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=1200)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "bench_strategy15.log"), "r") as f:
    log = f.read()

for line in log.split('\n'):
    if any(x in line for x in ['classes in', '===', '---', 't_module', 't_h1', 't_action',
                                 't_orbits', 't_convert', 'calls:', 'total_orbits',
                                 'total_points']):
        print(line.strip())

if stderr and 'Syntax warning' not in stderr[:200]:
    print(f"stderr: {stderr[:500]}")
