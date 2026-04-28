"""Test S15 partition [5,4,4,2] with orbital OFF. Expected: 4753.
This tests whether the slowdown is orbital-specific or general."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/s15_5442_off.log"

if os.path.exists(log_file.replace("/", os.sep)):
    os.remove(log_file.replace("/", os.sep))

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := false;

Print("\\n========== Partition [5,4,4,2] ORBITAL OFF ==========\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
result := FindFPFClassesForPartition(15, [5,4,4,2]);
t1 := Runtime() - t0;
Print("  [5,4,4,2]: ", Length(result), " (expected 4753) ", t1, "ms\\n");
if Length(result) = 4753 then
    Print("  [5,4,4,2] PASSED\\n");
else
    Print("  [5,4,4,2] FAILED (delta = ", 4753 - Length(result), ")\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_s15_5442_off.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s15_5442_off.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting [5,4,4,2] OFF test at {time.strftime('%H:%M:%S')}")
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
        if any(x in line for x in ['==========', 'PASS', 'FAIL', 'expected', 'delta', '5,4,4,2', 'Final']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
