"""Test S12 fresh (no cache) with orbital ON and affine fix."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/s12_fresh.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
# Do NOT load lift_cache - compute fresh
# But DO load FPF subdirect cache for speed
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;

# Clear LIFT_CACHE to force recomputation of S11 and S12
# Keep S1-S10 cached for speed
for kk in [11, 12] do
    if IsBound(LIFT_CACHE.(String(kk))) then
        Unbind(LIFT_CACHE.(String(kk)));
    fi;
od;

t0 := Runtime();
count := CountAllConjugacyClassesFast(12);
t := Runtime() - t0;
Print("\\nS12 = ", count, " (expected 10723) ", t, "ms\\n");
if count = 10723 then
    Print("S12 PASSED\\n");
else
    Print("S12 FAILED (delta = ", 10723 - count, ")\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_s12_fresh.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s12_fresh.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 fresh test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=3600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(x in line for x in ['S12', 'S11', 'PASS', 'FAIL', 'Total S_1']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
