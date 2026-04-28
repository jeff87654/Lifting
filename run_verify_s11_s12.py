"""
Verify S11 and S12 with current code.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/verify_s11_s12.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;

# S11
Print("Computing S11...\\n");
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
r11 := CountAllConjugacyClassesFast(11);
Print("S11 = ", r11, " (", (Runtime()-t0)/1000.0, "s)\\n");
Print("Expected: 3094\\n\\n");

# S12
Print("Computing S12...\\n");
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
r12 := CountAllConjugacyClassesFast(12);
Print("S12 = ", r12, " (", (Runtime()-t0)/1000.0, "s)\\n");
Print("Expected: 10723\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_verify_s11_s12.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_s11_s12.g"

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

stdout, stderr = process.communicate(timeout=3600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if line.startswith('S') or 'Expected' in line or 'Total' in line:
        print(line.strip())
