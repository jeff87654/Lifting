"""
Verify: is it Size(P) on the SAME object, or just having computed it before?
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/repro_size.log"

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
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Test 1: Size(P) on same P object
Print("=== Test 1: Size(P) on same P ===\\n");
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P);
Print("Size(P) = ", x, "\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result1 := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result 1: ", Length(result1), "\\n\\n");

# Test 2: Size on a COPY of P, then use original fresh P
Print("=== Test 2: Size on copy, use fresh P ===\\n");
P_fresh := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
P_copy := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P_copy);
Print("Size(P_copy) = ", x, "\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result2 := FindFPFClassesByLifting(P_fresh, shifted, offs, N);
Print("Result 2: ", Length(result2), "\\n\\n");

# Test 3: HasSize attribute test - does SetSize cause the same issue?
Print("=== Test 3: SetSize on P ===\\n");
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P3, 2592);
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result3 := FindFPFClassesByLifting(P3, shifted, offs, N);
Print("Result 3: ", Length(result3), "\\n\\n");

# Test 4: HasStabChainMutable test
Print("=== Test 4: StabChain on P ===\\n");
P4 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
StabChain(P4);
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result4 := FindFPFClassesByLifting(P4, shifted, offs, N);
Print("Result 4: ", Length(result4), "\\n\\n");

# Test 5: Fresh P, no Size
Print("=== Test 5: fresh P, no Size ===\\n");
P5 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result5 := FindFPFClassesByLifting(P5, shifted, offs, N);
Print("Result 5: ", Length(result5), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_repro_size.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_repro_size.g"

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
        if any(kw in line for kw in ['Test', 'Result', 'orbital', 'Size']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
