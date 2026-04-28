###############################################################################
# run_full_verify.py - Full S2-S10 verification
###############################################################################

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/full_verify.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

known := rec();
known.2 := 2; known.3 := 4; known.4 := 11; known.5 := 19;
known.6 := 56; known.7 := 96; known.8 := 296;
known.9 := 554; known.10 := 1593;
known.11 := 3094;

allPass := true;
totalStart := Runtime();

for n in [2..10] do
    t := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t) / 1000.0;
    expected := known.(n);
    if count = expected then
        Print("S_", n, " = ", count, " PASS (", elapsed, "s)\\n");
    else
        Print("S_", n, " = ", count, " FAIL (expected ", expected, ") (", elapsed, "s)\\n");
        allPass := false;
    fi;
od;

totalTime := (Runtime() - totalStart) / 1000.0;
Print("\\n==========================================\\n");
if allPass then
    Print("ALL PASS in ", totalTime, "s\\n");
else
    Print("SOME FAILURES in ", totalTime, "s\\n");
fi;

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "full_verify.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/full_verify.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S2-S10 verification...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

log_path = os.path.join(LIFTING_DIR, "full_verify.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    # Print just the key results
    for line in log.split("\n"):
        if "S_" in line or "PASS" in line or "FAIL" in line or "====" in line or "ALL" in line or "SOME" in line:
            print(line)
else:
    print("No log file produced")
    if stderr:
        print(f"stderr: {stderr[:500]}")
