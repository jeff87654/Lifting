"""Test S14 with orbital ON (using cached S1-S13)."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/s14_orbital_test.log"

if os.path.exists(log_file.replace("/", os.sep)):
    os.remove(log_file.replace("/", os.sep))

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;

# Clear S14 from cache to force recomputation
if IsBound(LIFT_CACHE.("14")) then
    Unbind(LIFT_CACHE.("14"));
fi;

t0 := Runtime();
count := CountAllConjugacyClassesFast(14);
t := Runtime() - t0;
Print("S14 = ", count, " (expected 75154) ", t, "ms\\n");
if count = 75154 then
    Print("S14 PASSED\\n");
else
    Print("S14 FAILED (delta = ", 75154 - count, ")\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_s14_orbital_test.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s14_orbital_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S14 orbital test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=14400)
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
        if any(x in line for x in ['S14', 'PASS', 'FAIL', 'Total', 'expected', 'delta']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
