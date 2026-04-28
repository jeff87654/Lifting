import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_222222_no_c1.log"

gap_commands = f'''
LogTo("{log_file}");
Print("=== Test [2,2,2,2,2,2] without Phase C1 ===\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Warmup S2-S11
Print("Computing S2-S11 (warmup)...\\n");
t0 := Runtime();
CountAllConjugacyClassesFast(11);
Print("Warmup done in ", (Runtime()-t0)/1000.0, "s\\n\\n");

# Clear for the test
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

# Test [2,2,2,2,2,2]
Print("Testing [2,2,2,2,2,2]...\\n");
t0 := Runtime();
fpf := FindFPFClassesForPartition(12, [2,2,2,2,2,2]);
dt := (Runtime() - t0) / 1000.0;
count := Length(fpf);
Print("  Count: ", count, " (expected 113, diff=", count - 113, ") (", dt, "s)\\n");
if count = 113 then
    Print("  PASS\\n");
else
    Print("  FAIL\\n");
fi;

# Also test [2,2,2,2] from S8 as a sanity check
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();
Print("\\nTesting [2,2,2,2] from S8...\\n");
t0 := Runtime();
fpf8 := FindFPFClassesForPartition(8, [2,2,2,2]);
dt := (Runtime() - t0) / 1000.0;
count8 := Length(fpf8);
# Reference: S8 total = 296. FPF(S8) = 296 - 96 = 200.
# The [2,2,2,2] partition contributes some of those.
Print("  [2,2,2,2] count: ", count8, " (", dt, "s)\\n");

Print("\\n=== Test Complete ===\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_222222_no_c1.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_222222_no_c1.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=600)
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

if os.path.exists(log_file.replace("/", "\\")):
    with open(log_file.replace("/", "\\"), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(w in line for w in ['Count', 'PASS', 'FAIL', 'Test', 'count', 'Warmup']):
            print(line)
else:
    print("No log file!")
    print("STDERR:", stderr[:2000])
