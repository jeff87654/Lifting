"""Benchmark [6,4,3] of S13 - one of the slowest partitions."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

log_file = "C:/Users/jeffr/Downloads/Lifting/bench_s13_slow.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load S1-S12 from cache (skip recomputation)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF and H^1 caches (want fresh computation for partition)
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Benchmark [6,4,3] - was 340s before all optimizations
Print("Benchmarking [6,4,3] of S13...\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(13, [6,4,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[6,4,3]: ", Length(result), " classes in ", elapsed, "s\\n");

# Also try [5,4,4] - was 425s
Print("\\nBenchmarking [5,4,4] of S13...\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result := FindFPFClassesForPartition(13, [5,4,4]);
elapsed := (Runtime() - t0) / 1000.0;
Print("[5,4,4]: ", Length(result), " classes in ", elapsed, "s\\n");

# Stats
if IsBound(H1_TIMING_STATS) then
    Print("H^1 calls: ", H1_TIMING_STATS.h1_calls, "\\n");
    Print("Coprime skips: ", H1_TIMING_STATS.coprime_skips, "\\n");
fi;

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "bench_s13_slow.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_s13_slow.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S13 partition benchmarks...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=3600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "bench_s13_slow.log"), "r") as f:
    log = f.read()

# Show key results
for line in log.split('\n'):
    if any(x in line for x in ['classes in', 'H^1', 'Coprime', 'Benchmarking']):
        print(line.strip())

if stderr and 'Syntax warning' not in stderr[:200]:
    print(f"stderr: {stderr[:500]}")
