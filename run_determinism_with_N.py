"""
Test if passing N to FindFPFClassesByLifting causes different results.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/determinism_withN.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
T63_2 := TransitiveGroup(3, 2);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Test 1: pass N
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();
result1 := FindFPFClassesByLifting(P, shifted, offs, N);
Print("With N: ", Length(result1), "\\n");

# Test 2: don't pass N
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();
result2 := FindFPFClassesByLifting(P, shifted, offs);
Print("Without N: ", Length(result2), "\\n");

# Test 3: pass N again
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();
result3 := FindFPFClassesByLifting(P, shifted, offs, N);
Print("With N again: ", Length(result3), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_determinism_withN.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_determinism_withN.g"

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

with open(r"C:\Users\jeffr\Downloads\Lifting\determinism_withN.log", "r") as f:
    log = f.read()
for line in log.split('\n'):
    if 'With' in line or 'Without' in line or 'orbital' in line.lower() or 'Result' in line:
        print(line.strip())
