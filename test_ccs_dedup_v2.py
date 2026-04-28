"""Test CCS dedup Union-Find optimization with S2-S10."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = os.path.join(LIFTING_DIR, "gap_output_ccs_dedup_v2.log")

gap_commands = f'''
LogTo("{log_file.replace(chr(92), '/')}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();

# Clear all caches for fresh computation
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("Testing S2-S10 with CCS Union-Find dedup...\\n");
t0 := Runtime();
for n in [2..10] do
    t1 := Runtime();
    c := CountAllConjugacyClassesFast(n);
    Print("S", n, " = ", c, " (", Runtime()-t1, "ms)\\n");
od;
Print("Total time: ", Runtime()-t0, "ms\\n");

Print("\\nExpected: S2=2, S3=4, S4=11, S5=19, S6=56, S7=96, S8=296, S9=554, S10=1593\\n");
if LIFT_CACHE.(String(10)) = 1593 then
    Print("S10 PASS\\n");
else
    Print("S10 FAIL: got ", LIFT_CACHE.(String(10)), "\\n");
fi;
LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "temp_test_ccs_dedup_v2.g")
with open(script_file, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_ccs_dedup_v2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 test at {time.strftime('%H:%M:%S')}")
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

with open(log_file, "r") as f:
    log = f.read()

# Print last 30 lines
lines = log.strip().split('\n')
for line in lines[-30:]:
    print(line)
