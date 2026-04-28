import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_goursat_s11_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S11 data
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF cache for fresh computation
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== S11 from cache ===\\n");
t0 := Runtime();
count := CountAllConjugacyClassesFast(11);
Print("S11 = ", count, " (", Runtime()-t0, "ms)\\n");

Print("\\n=== Testing [6,6] partition of S12 ===\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result := FindFPFClassesForPartition(12, [6,6]);
Print("[6,6] FPF classes: ", Length(result), " (", Runtime()-t0, "ms)\\n");

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

stdout, stderr = process.communicate(timeout=1800)
print(f"GAP finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
print(log[-3000:])
