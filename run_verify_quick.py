"""
Quick verification: S2-S10 with current code.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/verify_quick.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();

t0 := Runtime();
for n in [2..10] do
    LIFT_CACHE := rec();
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();
    result := CountAllConjugacyClassesFast(n);
    Print("S", n, " = ", result, "\\n");
od;
Print("Total time: ", (Runtime() - t0) / 1000.0, "s\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_verify_quick.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_quick.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if line.startswith('S') or 'Total' in line:
        print(line.strip())
