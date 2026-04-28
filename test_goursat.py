import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_goursat_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Testing S2-S10 with Goursat optimization ===\\n");
t0 := Runtime();
for n in [2..10] do
    t1 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    t2 := Runtime();
    Print("S", n, " = ", count, " (", t2-t1, "ms)\\n");
od;
Print("Total time: ", Runtime()-t0, "ms\\n");

Print("\\n=== Testing S3 x S3 (unit test) ===\\n");
TestLiftingS3xS3();

Print("\\n=== Testing S4 x S4 (unit test) ===\\n");
TestLiftingS4xS4();

Print("\\nAll tests complete.\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}")
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
print(f"GAP finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
print(log)
