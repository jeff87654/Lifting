"""Verify affine fix: check S11 and P-conjugacy coverage on the failing combo."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_verify.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# ========== TEST 1: S11 with orbital ON ==========
Print("\\n========== TEST 1: S11 ==========\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
LIFT_CACHE := rec();

t0 := Runtime();
count := CountAllConjugacyClassesFast(11);
t := Runtime() - t0;
Print("S11 = ", count, " (expected 3094) ", t, "ms\\n");
if count = 3094 then
    Print("S11 PASSED\\n");
else
    Print("S11 FAILED (delta = ", 3094 - count, ")\\n");
fi;

# ========== TEST 2: Combo P-conjugacy check ==========
Print("\\n========== TEST 2: Combo [6,5] x [6,8] x [3,2] ==========\\n");

f1 := TransitiveGroup(6, 5);
f2 := TransitiveGroup(6, 8);
f3 := TransitiveGroup(3, 2);

shifted := [];
offs := [];
off := 0;
for factor in [f1, f2, f3] do
    Add(offs, off);
    degree := NrMovedPoints(factor);
    shift_perm := MappingPermListList([1..degree], [off+1..off+degree]);
    Add(shifted, Group(List(GeneratorsOfGroup(factor), g -> g^shift_perm)));
    off := off + degree;
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

# Run OFF
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_off := FindFPFClassesByLifting(P, shifted, offs);
Print("OFF: ", Length(results_off), "\\n");

# Run ON
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_on := FindFPFClassesByLifting(P, shifted, offs);
Print("ON: ", Length(results_on), "\\n");

# Check: is every OFF result P-conjugate to some ON result?
unmatched := 0;
for i in [1..Length(results_off)] do
    found := false;
    for j in [1..Length(results_on)] do
        if Size(results_off[i]) = Size(results_on[j]) then
            if RepresentativeAction(P, results_off[i], results_on[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        unmatched := unmatched + 1;
        Print("  OFF[", i, "] (|G|=", Size(results_off[i]),
              " ", StructureDescription(results_off[i]),
              ") NOT matched to any ON group\\n");
    fi;
od;
Print("Unmatched OFF groups: ", unmatched, "\\n");
if unmatched = 0 then
    Print("ALL OFF groups covered by ON reps - CORRECT\\n");
fi;

# Also check: any ON groups not matched to OFF?
unmatched_on := 0;
for j in [1..Length(results_on)] do
    found := false;
    for i in [1..Length(results_off)] do
        if Size(results_on[j]) = Size(results_off[i]) then
            if RepresentativeAction(P, results_on[j], results_off[i]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        unmatched_on := unmatched_on + 1;
    fi;
od;
if unmatched_on > 0 then
    Print("WARNING: ", unmatched_on, " ON groups not in OFF list!\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_orbital_verify.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_orbital_verify.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting verification at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(x in line for x in ['TEST', 'S11', 'OFF', 'ON', 'PASS', 'FAIL',
                                     'Unmatched', 'matched', 'CORRECT', 'WARNING',
                                     'NOT', 'covered', 'delta']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
