"""
Test partition [6,6,3] of S15 via production code path.
Compare orbital ON vs OFF.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/s15_663.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Need S1-S14 cache for S15 computation
# lift_cache already provides this

# Test 1: orbital ON
Print("=== Test 1: orbital ON ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
result1 := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital ON: ", Length(result1), " classes\\n\\n");

# Test 2: orbital OFF
Print("=== Test 2: orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
result2 := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital OFF: ", Length(result2), " classes\\n\\n");

Print("Difference: ", Length(result2) - Length(result1), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s15_663.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s15_663.g"

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

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Test', 'Orbital', 'orbital', 'classes', 'Difference']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
