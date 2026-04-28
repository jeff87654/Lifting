"""
Simple trace: add TRACE_FPF flag to LiftThroughLayer output.
Compare which complements pass/fail FPF.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_simple.log"

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

Print("\\n=== Simple FPF trace ===\\n\\n");

# Build two P's
P1 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P1);
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

# Lift both through layers 1-7
series1 := RefinedChiefSeries(P1);
series2 := RefinedChiefSeries(P2);

USE_H1_ORBITAL := true;
current1 := [P1];
for i in [1..7] do
    ClearH1Cache();
    current1 := LiftThroughLayer(P1, series1[i], series1[i+1], current1, shifted, offs, fail);
od;
Print("After 7 layers (stab): ", Length(current1), " parents\\n");

ClearH1Cache();
current2 := [P2];
for i in [1..7] do
    ClearH1Cache();
    current2 := LiftThroughLayer(P2, series2[i], series2[i+1], current2, shifted, offs, fail);
od;
Print("After 7 layers (fresh): ", Length(current2), " parents\\n\\n");

# Now manually trace layer 8
M1 := series1[8]; N1 := series1[9];
M2 := series2[8]; N2 := series2[9];

Print("Layer 8: |M|=", Size(M1), " |N|=", Size(N1), "\\n\\n");

# For stab P:
Print("=== STAB case ===\\n");
ClearH1Cache();
result1 := LiftThroughLayer(P1, M1, N1, current1, shifted, offs, fail);
Print("Stab result: ", Length(result1), "\\n");
Print("Stab sizes: ", SortedList(List(result1, Size)), "\\n\\n");

# For fresh P:
Print("=== FRESH case ===\\n");
ClearH1Cache();
result2 := LiftThroughLayer(P2, M2, N2, current2, shifted, offs, fail);
Print("Fresh result: ", Length(result2), "\\n");
Print("Fresh sizes: ", SortedList(List(result2, Size)), "\\n\\n");

# Compare: which sizes appear differently?
sizes1 := Collected(List(result1, Size));
sizes2 := Collected(List(result2, Size));
Print("Stab size distribution: ", sizes1, "\\n");
Print("Fresh size distribution: ", sizes2, "\\n\\n");

# For each result in stab that's NOT in fresh (by checking all pairs)
Print("Checking if stab results are in fresh (under P-conjugacy)...\\n");
for i in [1..Length(result1)] do
    found := false;
    for j in [1..Length(result2)] do
        if Size(result1[i]) = Size(result2[j]) then
            if result1[i] = result2[j] then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  stab[", i, "]: |H|=", Size(result1[i]), " NOT in fresh (exact match)\\n");
    fi;
od;

Print("\\nChecking under N-conjugacy...\\n");
for i in [1..Length(result1)] do
    found := false;
    for j in [1..Length(result2)] do
        if Size(result1[i]) = Size(result2[j]) then
            if RepresentativeAction(N, result1[i], result2[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  stab[", i, "]: |H|=", Size(result1[i]), " NOT in fresh (N-conj)\\n");
    fi;
od;

Print("\\nReverse: fresh results not in stab (under N-conjugacy)...\\n");
for i in [1..Length(result2)] do
    found := false;
    for j in [1..Length(result1)] do
        if Size(result2[i]) = Size(result1[j]) then
            if RepresentativeAction(N, result2[i], result1[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  fresh[", i, "]: |H|=", Size(result2[i]), " NOT in stab (N-conj)\\n");
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_simple.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_simple.g"

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

stdout, stderr = process.communicate(timeout=1200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    for line in stderr.strip().split('\n'):
        if 'Error' in line:
            print(f"STDERR: {line}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['After', 'STAB', 'FRESH', 'result', 'sizes', 'size',
                                      'NOT', 'Checking', 'Reverse', 'Layer', 'distribution']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
