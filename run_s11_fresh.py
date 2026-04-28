###############################################################################
# run_s11_fresh.py - Compute S11 fresh (clear S11 cache entry)
###############################################################################

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/s11_fresh.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches but remove S11
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(LIFT_CACHE.11) then Unbind(LIFT_CACHE.11); fi;

# Clear runtime caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t := Runtime();
count := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t) / 1000.0;

Print("\\n==========================================\\n");
Print("S_11 = ", count, " (", elapsed, "s)\\n");
if count = 3094 then
    Print("PASS\\n");
else
    Print("FAIL (expected 3094)\\n");
fi;

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "s11_fresh.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/s11_fresh.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Computing S11 fresh (with S1-S10 from cache)...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=1200)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

log_path = os.path.join(LIFTING_DIR, "s11_fresh.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    # Print key partition results and summary
    for line in log.split("\n"):
        if any(k in line for k in ["S_11", "PASS", "FAIL", "====", "Total", "Partition", "=> ", "classes"]):
            print(line)
else:
    print("No log file produced")
    if stderr:
        print(f"stderr: {stderr[:500]}")
