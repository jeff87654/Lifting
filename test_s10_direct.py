#!/usr/bin/env python3
"""Speed test for S10 with H^1 enabled - direct output."""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("\\nUSE_H1_COMPLEMENTS = ", USE_H1_COMPLEMENTS, "\\n\\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
totalTime := Runtime() - startTime;
Print("\\n==========================================\\n");
Print("S10 RESULT: ", result, " (expected 1593)\\n");
Print("Total time: ", Float(totalTime/1000), " seconds (", Float(totalTime/60000), " minutes)\\n");
if result = 1593 then Print("STATUS: PASS\\n"); else Print("STATUS: FAIL\\n"); fi;
PrintH1TimingStats();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S10 speed test...", flush=True)

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10.g"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env,
    cwd=gap_runtime,
    bufsize=1
)

# Stream output line by line
for line in process.stdout:
    print(line, end='', flush=True)

process.wait()
print(f"\nProcess exited with code: {process.returncode}")
