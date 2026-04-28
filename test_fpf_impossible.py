"""Test FPF impossibility optimization: verify S2-S10 correctness."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_fpf_impossible_output.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Testing S2-S10 with FPF impossibility optimization ===\\n");
t0 := Runtime();

expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

allPass := true;
for n in [2..10] do
    t1 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := Runtime() - t1;
    if count = expected[n] then
        Print("S", n, " = ", count, " PASS (", elapsed, "ms)\\n");
    else
        Print("S", n, " = ", count, " FAIL (expected ", expected[n], ") (", elapsed, "ms)\\n");
        allPass := false;
    fi;
od;

total := Runtime() - t0;
Print("\\nTotal time: ", total, "ms\\n");
if allPass then
    Print("ALL PASS\\n");
else
    Print("SOME TESTS FAILED\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_fpf_impossible_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_fpf_impossible_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 verification test at {time.strftime('%H:%M:%S')}")
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
print(f"Process finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
print(log)
