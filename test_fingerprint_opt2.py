"""Test S2-S10 after fixed H^1 fingerprint optimization (non-solvable groups keep identity)."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

log_file = "C:/Users/jeffr/Downloads/Lifting/test_fingerprint_opt2.log"

gap_code = f'''
LogTo("{log_file}");
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
        Print("S", n, " = ", result, " PASS (", elapsed, "s)\\n");
    else
        Print("S", n, " = ", result, " FAIL (expected ", expected[n], ")\\n");
        allPass := false;
    fi;
od;

Print("\\nTotal CPU: ", (Runtime() - t_total) / 1000.0, "s\\n");

# Print H1 cache stats
Print("\\nH1 cache entries: ", Length(RecNames(H1_CACHE)), "\\n");
if IsBound(H1_TIMING_STATS) then
    Print("H1 calls: ", H1_TIMING_STATS.h1_calls, "\\n");
    Print("Cache hits: ", H1_TIMING_STATS.cache_hits, "\\n");
    Print("Coprime skips: ", H1_TIMING_STATS.coprime_skips, "\\n");
    Print("Fallback calls: ", H1_TIMING_STATS.fallback_calls, "\\n");
    Print("H1 time: ", H1_TIMING_STATS.h1_time, "ms\\n");
fi;

if allPass then
    Print("\\nALL PASS (fingerprint opt v2)\\n");
else
    Print("\\nSOME FAILED\\n");
fi;

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "test_fingerprint_opt2.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_fingerprint_opt2.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S2-S10 with fixed fingerprint optimization...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "test_fingerprint_opt2.log"), "r") as f:
    log = f.read()

# Show key results
for line in log.split('\n'):
    if any(x in line for x in ['PASS', 'FAIL', 'ALL', 'Total', 'SOME', 'cache', 'Cache',
                                 'H1', 'Fallback', 'fallback', 'invalid', 'falling']):
        print(line.strip())

# Check for warnings
warning_count = log.count('invalid')
if warning_count > 0:
    print(f"\nWARNING: {warning_count} 'invalid' mentions in log")
else:
    print("\nNo invalid complement warnings (good!)")

if stderr and 'Syntax warning' not in stderr[:200]:
    print(f"stderr: {stderr[:500]}")
