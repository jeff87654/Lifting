"""
Minimal reproducer: what causes the difference between debug_combo2 (17) and match_debug (14)?
Test if ResetH1TimingStats() is the culprit.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/minimal_repro.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
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

# Test A: WITH ResetH1TimingStats (like debug_combo2)
Print("=== Test A: with ResetH1TimingStats ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();
resultA := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result A: ", Length(resultA), "\\n\\n");

# Test B: WITHOUT ResetH1TimingStats (like match_debug)
Print("=== Test B: without ResetH1TimingStats ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
resultB := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result B: ", Length(resultB), "\\n\\n");

# Test C: with ResetH1TimingStats again
Print("=== Test C: with ResetH1TimingStats again ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();
resultC := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result C: ", Length(resultC), "\\n\\n");

# Test D: different cache clearing order
Print("=== Test D: clear caches after USE_H1_ORBITAL ===\\n");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
USE_H1_ORBITAL := true;
ClearH1Cache();
resultD := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result D: ", Length(resultD), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_minimal_repro.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_minimal_repro.g"

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

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Test', 'Result', 'orbital']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
