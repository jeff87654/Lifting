"""Test S13 with orbital ON to verify no regression from affine fix."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/s13_orbital_test.log"

if os.path.exists(log_file.replace("/", os.sep)):
    os.remove(log_file.replace("/", os.sep))

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;

# Compute S13 using cached S1-S12
t0 := Runtime();
count := CountAllConjugacyClassesFast(13);
t := Runtime() - t0;
Print("S13 = ", count, " (expected 20832) ", t, "ms\\n");
if count = 20832 then
    Print("S13 PASSED\\n");
else
    Print("S13 FAILED (delta = ", 20832 - count, ")\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_s13_orbital_test.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s13_orbital_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S13 orbital test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
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
        if any(x in line for x in ['S13', 'PASS', 'FAIL', 'Total', 'expected', 'delta']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
