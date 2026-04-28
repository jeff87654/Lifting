"""
Quick test: just the one combo [T66_5, T66_8, T63_2] via production path.
No Size(P) before lifting.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/quick_663.log"

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

DedupUnderN := function(results, N_group)
    local reps, H, found, i;
    reps := [];
    for H in results do
        found := false;
        for i in [1..Length(reps)] do
            if Size(H) = Size(reps[i]) then
                if RepresentativeAction(N_group, H, reps[i]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(reps, H);
        fi;
    od;
    return reps;
end;

# Test 1: orbital ON, fresh P
Print("=== Test 1: orbital ON, fresh P ===\\n");
P1 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
r1 := FindFPFClassesByLifting(P1, shifted, offs, N);
Print("Result: ", Length(r1), " N-classes: ", Length(DedupUnderN(r1, N)), "\\n\\n");

# Test 2: orbital OFF, fresh P
Print("=== Test 2: orbital OFF, fresh P ===\\n");
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
r2 := FindFPFClassesByLifting(P2, shifted, offs, N);
Print("Result: ", Length(r2), " N-classes: ", Length(DedupUnderN(r2, N)), "\\n\\n");

# Test 3: orbital ON, Size(P) called first
Print("=== Test 3: orbital ON, Size(P) first ===\\n");
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P3);
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
r3 := FindFPFClassesByLifting(P3, shifted, offs, N);
Print("Result: ", Length(r3), " N-classes: ", Length(DedupUnderN(r3, N)), "\\n\\n");

# Test 4: orbital ON, fresh P, series[8] forced to have same gen
Print("=== Test 4: orbital ON, fresh P (run 2) ===\\n");
P4 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
r4 := FindFPFClassesByLifting(P4, shifted, offs, N);
Print("Result: ", Length(r4), " N-classes: ", Length(DedupUnderN(r4, N)), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_quick_663.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_quick_663.g"

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
    if any(kw in line for kw in ['Test', 'Result', 'classes']):
        print(line.strip())
