"""
Narrow down: is it Size(P), TransitiveIdentification, or Size(N) that causes the change?
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/repro_narrow.log"

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

# Test 1: Size(P) only
Print("\\n=== Test 1: Size(P) then compute ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
x := Size(P);
result1 := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result 1: ", Length(result1), "\\n\\n");

# Test 2: TransitiveIdentification only
Print("=== Test 2: TransitiveIdentification then compute ===\\n");
# Rebuild P from scratch to clear any cache
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
x := List(factors, f -> TransitiveIdentification(f));
result2 := FindFPFClassesByLifting(P2, shifted, offs, N);
Print("Result 2: ", Length(result2), "\\n\\n");

# Test 3: Size(N) only
Print("=== Test 3: Size(N) then compute ===\\n");
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
x := Size(N);
result3 := FindFPFClassesByLifting(P3, shifted, offs, N);
Print("Result 3: ", Length(result3), "\\n\\n");

# Test 4: Nothing before compute
Print("=== Test 4: clean compute ===\\n");
P4 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result4 := FindFPFClassesByLifting(P4, shifted, offs, N);
Print("Result 4: ", Length(result4), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_repro_narrow.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_repro_narrow.g"

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
