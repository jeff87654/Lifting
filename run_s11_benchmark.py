###############################################################################
# run_s11_benchmark.py - S11 benchmark to measure hom_P optimization
###############################################################################

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/s11_benchmark.log"

gap_code = f'''
LogTo("{log_file}");
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
    Print("S_11 = ", count, " PASS (", elapsed, "s)\\n");
else
    Print("S_11 = ", count, " FAIL (expected 3094) (", elapsed, "s)\\n");
fi;

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "s11_benchmark.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/s11_benchmark.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S11 benchmark (S10 from cache)...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

log_path = os.path.join(LIFTING_DIR, "s11_benchmark.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    for line in log.split("\n"):
        if "S_11" in line or "PASS" in line or "FAIL" in line or "LiftThrough" in line:
            print(line)
else:
    print("No log file produced")
    if stderr:
        print(f"stderr: {stderr[:500]}")
