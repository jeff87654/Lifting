"""Test coprime-priority chief series reordering on S2-S12.

Verifies that CoprimePriorityChiefSeries doesn't break any counts.
"""
import subprocess
import os
import time

LOG_FILE = "C:/Users/jeffr/Downloads/Lifting/test_coprime_reorder.log"

gap_commands = f'''
LogTo("{LOG_FILE}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S16 counts for recursive calls
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear the lift cache entries we want to test so they recompute
Unbind(LIFT_CACHE.("2"));
Unbind(LIFT_CACHE.("3"));
Unbind(LIFT_CACHE.("4"));
Unbind(LIFT_CACHE.("5"));
Unbind(LIFT_CACHE.("6"));
Unbind(LIFT_CACHE.("7"));
Unbind(LIFT_CACHE.("8"));
Unbind(LIFT_CACHE.("9"));
Unbind(LIFT_CACHE.("10"));
Unbind(LIFT_CACHE.("11"));
Unbind(LIFT_CACHE.("12"));

# Expected OEIS values
OEIS := rec();
OEIS.("2") := 2;
OEIS.("3") := 4;
OEIS.("4") := 11;
OEIS.("5") := 19;
OEIS.("6") := 56;
OEIS.("7") := 96;
OEIS.("8") := 296;
OEIS.("9") := 554;
OEIS.("10") := 1593;
OEIS.("11") := 3094;
OEIS.("12") := 10723;

allPass := true;
for nn in [2..12] do
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
    result := CountAllConjugacyClassesFast(nn);
    expected := OEIS.(String(nn));
    if result = expected then
        Print("S", nn, " = ", result, " PASS\\n");
    else
        Print("S", nn, " = ", result, " FAIL (expected ", expected, ")\\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\\nALL TESTS PASSED\\n");
else
    Print("\\nSOME TESTS FAILED\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_coprime.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_coprime.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running coprime-priority chief series test S2-S12...")
t0 = time.time()
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")

with open(LOG_FILE, "r") as f:
    log = f.read()

# Print only the summary lines
for line in log.split('\n'):
    if 'PASS' in line or 'FAIL' in line or 'ALL TESTS' in line:
        print(line)
