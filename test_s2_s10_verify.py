import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_s2_s10_verify.log"

gap_commands = f'''
LogTo("{log_file}");
Print("=== S2-S10 Verification (Phase C1 + series stabilizer) ===\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Reference OEIS A000638 values
ref := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

Print("Computing S2-S10...\\n");
t0 := Runtime();

for n in [2..10] do
    t1 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    dt := (Runtime() - t1) / 1000.0;
    expected := ref[n-1];
    if count = expected then
        Print("  S", n, " = ", count, " PASS (", dt, "s)\\n");
    else
        Print("  S", n, " = ", count, " FAIL (expected ", expected, ", diff=", count-expected, ") (", dt, "s)\\n");
    fi;
od;

total_time := (Runtime() - t0) / 1000.0;
Print("\\nTotal time: ", total_time, "s\\n");
Print("\\n=== Test Complete ===\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s2_s10_verify.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s2_s10_verify.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 verification at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=600)
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

log_path = log_file.replace("/", "\\")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(w in line for w in ['PASS', 'FAIL', 'Total', 'Test', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10']):
            print(line)
else:
    print("No log file!")
    print("STDERR:", stderr[:2000])
