"""
Test the fix: removed FPF filter from orbital method.
Both with and without Size(P) should give the same result.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_fix.log"

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

# Test 1: with Size(P) (previously gave 17)
Print("=== Test 1: with Size(P) ===\\n");
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P);
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result1 := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result 1: ", Length(result1), "\\n\\n");

# Test 2: without Size(P) (previously gave 14)
Print("=== Test 2: without Size(P) ===\\n");
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result2 := FindFPFClassesByLifting(P2, shifted, offs, N);
Print("Result 2: ", Length(result2), "\\n\\n");

# Test 3: with StabChain(P) (previously gave 17)
Print("=== Test 3: with StabChain(P) ===\\n");
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
StabChain(P3);
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result3 := FindFPFClassesByLifting(P3, shifted, offs, N);
Print("Result 3: ", Length(result3), "\\n\\n");

# N-dedup all
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

Print("Dedup 1: ", Length(result1), " -> ", Length(DedupUnderN(result1, N)), "\\n");
Print("Dedup 2: ", Length(result2), " -> ", Length(DedupUnderN(result2, N)), "\\n");
Print("Dedup 3: ", Length(result3), " -> ", Length(DedupUnderN(result3, N)), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_fix.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_fix.g"

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
        if any(kw in line for kw in ['Test', 'Result', 'orbital', 'Dedup']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
