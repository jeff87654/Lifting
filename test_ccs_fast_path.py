"""Test CCS fast path: verify S2-S10 still correct after adding CCS fast path for non-abelian groups."""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_ccs_output.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for a fresh run
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("\\n=== Testing S2-S10 with CCS fast path ===\\n\\n");

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

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_ccs.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_ccs.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 test at {time.strftime('%H:%M:%S')}")
print(f"Log: {log_file}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}, exit code: {process.returncode}")

if os.path.exists(log_file.replace("/", "\\")):
    with open(log_file.replace("/", "\\"), "r") as f:
        log = f.read()
    # Print just the key results
    for line in log.split("\n"):
        if any(k in line for k in ["S", "PASS", "FAIL", "Total", "CCS fast", "SmallGroup fast"]):
            print(line)
else:
    print("No log file produced!")
    print("STDOUT:", stdout[:2000])
    print("STDERR:", stderr[:2000])
