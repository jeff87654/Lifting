"""
Find the EXACT missing classes in [6,6,3] orbital computation.

Strategy:
1. Run [6,6,3] with orbital OFF -> get all FPF subgroups (correct answer: 3248)
2. Run [6,6,3] with orbital ON -> get all FPF subgroups (buggy: 3246)
3. For each class in OFF that's missing from ON, identify:
   - Which combo it came from
   - What the subgroup looks like (size, generators, etc.)

This will tell us exactly what the orbital method is incorrectly merging/dropping.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/find_missing_classes.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Run 1: Orbital OFF (correct)
Print("=== Run 1: orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result_off := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital OFF: ", Length(result_off), " classes (", (Runtime()-t0)/1000.0, "s)\\n\\n");

# Run 2: Orbital ON (buggy)
Print("=== Run 2: orbital ON ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result_on := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital ON: ", Length(result_on), " classes (", (Runtime()-t0)/1000.0, "s)\\n\\n");

Print("Difference: ", Length(result_off) - Length(result_on), "\\n");

if Length(result_off) <> Length(result_on) then
    Print("\\n*** FINDING MISSING CLASSES ***\\n");

    # Build normalizer for conjugacy testing
    N := BuildConjugacyTestGroup(15, [6, 6, 3]);
    Print("Normalizer |N| = ", Size(N), "\\n");

    # For each class in result_off, check if it exists in result_on
    missing := [];
    for i in [1..Length(result_off)] do
        H_off := result_off[i];
        found := false;
        for j in [1..Length(result_on)] do
            H_on := result_on[j];
            if Size(H_off) = Size(H_on) then
                if RepresentativeAction(N, H_off, H_on) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(missing, i);
            Print("\\n--- Missing class #", Length(missing), " (index ", i, " in OFF result) ---\\n");
            Print("  |H| = ", Size(H_off), "\\n");
            Print("  Generators: ", GeneratorsOfGroup(H_off), "\\n");
            Print("  Orbits: ", List(Orbits(H_off, MovedPoints(H_off)), Length), "\\n");
            Print("  MovedPoints: ", MovedPoints(H_off), "\\n");
            # Check which orbits the subgroup has
            orbs := Orbits(H_off, [1..15]);
            Print("  All orbits: ", List(orbs, Length), "\\n");
            # Check transitivity on [1..6], [7..12], [13..15]
            Print("  Restriction to [1..6]: transitive=", IsTransitive(H_off, [1..6]), "\\n");
            Print("  Restriction to [7..12]: transitive=", IsTransitive(H_off, [7..12]), "\\n");
            Print("  Restriction to [13..15]: transitive=", IsTransitive(H_off, [13..15]), "\\n");
        fi;
    od;

    Print("\\n=== SUMMARY ===\\n");
    Print("Total missing: ", Length(missing), " classes\\n");
    Print("Missing indices: ", missing, "\\n");

    # Also check if any class in result_on is NOT in result_off (shouldn't happen)
    extra := [];
    for j in [1..Length(result_on)] do
        H_on := result_on[j];
        found := false;
        for i in [1..Length(result_off)] do
            H_off := result_off[i];
            if Size(H_on) = Size(H_off) then
                if RepresentativeAction(N, H_on, H_off) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(extra, j);
            Print("EXTRA class in ON (index ", j, "): |H|=", Size(H_on), "\\n");
        fi;
    od;
    Print("Extra classes in ON: ", Length(extra), "\\n");
else
    Print("Counts match! No missing classes.\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_find_missing.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_find_missing.g"

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

stdout, stderr = process.communicate(timeout=14400)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['===', 'Orbital', 'Difference', 'Missing', 'missing',
                                      'EXTRA', 'extra', '|H|', 'Generators', 'Orbits',
                                      'transitive', 'SUMMARY', 'Total', 'indices',
                                      'Normalizer', '---', 'Restriction', 'match']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
