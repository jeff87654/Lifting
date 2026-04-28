"""Test CCS fast path v2: refined condition (numLayers >= 8)."""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_ccs_v2_output.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for a fresh run
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("\\n=== Testing S2-S10 with CCS fast path v2 (numLayers >= 8) ===\\n\\n");

t0 := Runtime();
for n in [2..10] do
    t1 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    Print("S", n, " = ", count, " (", Runtime() - t1, "ms)\\n");
od;
totalTime := Runtime() - t0;
Print("\\nTotal S2-S10 time: ", totalTime, "ms\\n");

# Verify expected values
expected := rec(
    s2 := 2, s3 := 4, s4 := 11, s5 := 19,
    s6 := 56, s7 := 96, s8 := 296, s9 := 554, s10 := 1593
);

Print("\\n=== Verification ===\\n");
allPass := true;
for n in [2..10] do
    key := Concatenation("s", String(n));
    exp := expected.(key);
    actual := LIFT_CACHE.(String(n));
    if actual = exp then
        Print("S", n, ": PASS (", actual, ")\\n");
    else
        Print("S", n, ": FAIL (expected ", exp, ", got ", actual, ")\\n");
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

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_ccs_v2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_ccs_v2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 test v2 at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=900)
print(f"Finished at {time.strftime('%H:%M:%S')}, exit code: {process.returncode}")

if os.path.exists(log_file.replace("/", "\\")):
    with open(log_file.replace("/", "\\"), "r") as f:
        log = f.read()
    for line in log.split("\n"):
        if any(k in line for k in ["S", "PASS", "FAIL", "Total", "CCS fast", "SmallGroup fast", "ALL"]):
            print(line)
else:
    print("No log file!")
    print("STDOUT:", stdout[:2000])
    print("STDERR:", stderr[:2000])
