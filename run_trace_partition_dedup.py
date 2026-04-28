"""
Trace partition-level dedup for [6,6,3] to find where the missing class is lost.

The mystery: H_missing IS present in combo ON results (ON[11]), but the partition
count is 3247 instead of 3248. So the bug is in cross-combo dedup interaction.

Approach: For each combo of [6,6,3], compare ON vs OFF results and track which
specific classes survive the partition-level AddIfNotConjugate.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_partition_dedup.log"

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

N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Run the full partition computation with orbital ON, tracking H_missing
Print("\\n=== Orbital ON full partition ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

on_result := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("ON partition count: ", Length(on_result), "\\n");

# Check: is H_missing in on_result?
found_on := false;
for i in [1..Length(on_result)] do
    if Size(on_result[i]) = Size(H_missing) then
        if RepresentativeAction(N, on_result[i], H_missing) <> fail then
            found_on := true;
            Print("H_missing found in ON result at index ", i, "\\n");
            break;
        fi;
    fi;
od;
if not found_on then
    Print("H_missing NOT found in ON result!\\n");
fi;

# Now run with orbital OFF
Print("\\n=== Orbital OFF full partition ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

off_result := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("OFF partition count: ", Length(off_result), "\\n");

# Check: is H_missing in off_result?
found_off := false;
for i in [1..Length(off_result)] do
    if Size(off_result[i]) = Size(H_missing) then
        if RepresentativeAction(N, off_result[i], H_missing) <> fail then
            found_off := true;
            Print("H_missing found in OFF result at index ", i, "\\n");
            break;
        fi;
    fi;
od;
if not found_off then
    Print("H_missing NOT found in OFF result!\\n");
fi;

# Find classes in OFF but not ON (the difference)
Print("\\n=== Missing classes (in OFF but not ON) ===\\n");
missing := [];
for i in [1..Length(off_result)] do
    found := false;
    for j in [1..Length(on_result)] do
        if Size(off_result[i]) = Size(on_result[j]) then
            if RepresentativeAction(N, off_result[i], on_result[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Add(missing, off_result[i]);
        Print("Missing #", Length(missing), ": |H|=", Size(off_result[i]),
              " OFF[", i, "]\\n");
    fi;
od;
Print("Total missing: ", Length(missing), "\\n");

# Find classes in ON but not OFF (extras)
Print("\\n=== Extra classes (in ON but not OFF) ===\\n");
extras := [];
for i in [1..Length(on_result)] do
    found := false;
    for j in [1..Length(off_result)] do
        if Size(on_result[i]) = Size(off_result[j]) then
            if RepresentativeAction(N, on_result[i], off_result[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Add(extras, on_result[i]);
        Print("Extra #", Length(extras), ": |H|=", Size(on_result[i]),
              " ON[", i, "]\\n");
    fi;
od;
Print("Total extras: ", Length(extras), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_partition_dedup.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_partition_dedup.g"

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

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['===', 'partition count', 'H_missing', 'Missing',
                                      'Extra', 'Total', 'found', 'combo']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
