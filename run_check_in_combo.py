"""
Check if the missing class is directly present (up to N-conjugacy)
in the combo's raw ON results.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/check_in_combo.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# The missing class
H_missing := Group([
    ( 1, 4)( 2, 5)( 3, 6)( 7,12,10, 9)(14,15),
    ( 2, 4, 6)(13,14,15),
    ( 7,12,11)( 8,10, 9),
    ( 8,11)( 9,12),
    ( 7,10)( 9,12)
]);

Print("|H_missing| = ", Size(H_missing), "\\n");

# Build normalizer
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Set up combo
factors := [TransitiveGroup(6, 5), TransitiveGroup(6, 8), TransitiveGroup(3, 2)];
shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

# Run combo with orbital ON
Print("\\n=== Combo with orbital ON ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

series := RefinedChiefSeries(P);
parents := [P];
for i in [1..Length(series)-1] do
    ClearH1Cache();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
Print("ON result: ", Length(parents), " raw\\n");

# Check if H_missing is N-conjugate to any ON result
found_N := false;
for j in [1..Length(parents)] do
    if Size(parents[j]) = Size(H_missing) then
        if RepresentativeAction(N, parents[j], H_missing) <> fail then
            found_N := true;
            Print("H_missing IS N-conjugate to ON[", j, "] (|S|=", Size(parents[j]), ")\\n");
            break;
        fi;
    fi;
od;
if not found_N then
    Print("H_missing NOT N-conjugate to any ON result!\\n");

    # How many size-216 results in ON?
    count216 := 0;
    for j in [1..Length(parents)] do
        if Size(parents[j]) = 216 then
            count216 := count216 + 1;
        fi;
    od;
    Print("ON has ", count216, " results of size 216\\n");

    # Check P-conjugacy (broader than equality, narrower than N-conjugacy)
    found_P := false;
    for j in [1..Length(parents)] do
        if Size(parents[j]) = Size(H_missing) then
            if RepresentativeAction(P, parents[j], H_missing) <> fail then
                found_P := true;
                Print("H_missing IS P-conjugate to ON[", j, "]\\n");
                break;
            fi;
        fi;
    od;
    if not found_P then
        Print("H_missing NOT even P-conjugate to any ON result!\\n");
    fi;
fi;

# Run combo with orbital OFF
Print("\\n=== Combo with orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

parents_off := [P];
for i in [1..Length(series)-1] do
    ClearH1Cache();
    parents_off := LiftThroughLayer(P, series[i], series[i+1], parents_off, shifted, offs, fail);
od;
Print("OFF result: ", Length(parents_off), " raw\\n");

# Check if H_missing is N-conjugate to any OFF result
found_off_N := false;
for j in [1..Length(parents_off)] do
    if Size(parents_off[j]) = Size(H_missing) then
        if RepresentativeAction(N, parents_off[j], H_missing) <> fail then
            found_off_N := true;
            Print("H_missing IS N-conjugate to OFF[", j, "] (|S|=", Size(parents_off[j]), ")\\n");
            break;
        fi;
    fi;
od;
if not found_off_N then
    Print("H_missing NOT N-conjugate to any OFF result either!\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_check_in_combo.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_check_in_combo.g"

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
        if any(kw in line for kw in ['===', 'result', 'Result', 'H_missing',
                                      'N-conjugate', 'P-conjugate',
                                      'count', 'size 216']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
