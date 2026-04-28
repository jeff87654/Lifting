"""
Compare [6,6,3] partition results: orbital ON vs OFF.
Identify which N-conjugacy classes are missing.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/partition_compare.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Run with orbital OFF first
Print("=== Running [6,6,3] with orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result_off := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital OFF: ", Length(result_off), " classes (",
      (Runtime()-t0)/1000.0, "s)\\n\\n");

# Run with orbital ON
Print("=== Running [6,6,3] with orbital ON ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result_on := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Orbital ON: ", Length(result_on), " classes (",
      (Runtime()-t0)/1000.0, "s)\\n\\n");

Print("Difference: ", Length(result_off) - Length(result_on), "\\n\\n");

# Now find which classes from OFF are missing in ON
# Both lists should be N-deduped within each combo,
# but the partition-level dedup gives final counts.
#
# Compare: for each class in OFF, find if it's N-conjugate to some class in ON
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

Print("=== Finding missing classes ===\\n");
Print("Checking ", Length(result_off), " OFF classes against ",
      Length(result_on), " ON classes\\n");

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
        Add(missing, rec(idx := i, H := H_off));
        Print("  Missing class ", i, ": |H|=", Size(H_off),
              " gens=", GeneratorsOfGroup(H_off), "\\n");
    fi;
od;

Print("\\nTotal missing: ", Length(missing), "\\n");

# For each missing class, find which combo it came from
# by checking which transitive components it projects to
if Length(missing) > 0 then
    Print("\\n=== Identifying source combos for missing classes ===\\n");
    for m in missing do
        H := m.H;
        # Project to each orbit
        proj1 := Projection(SymmetricGroup(15), [1..6])(H);
        proj2 := Projection(SymmetricGroup(15), [7..12])(H);
        proj3 := Projection(SymmetricGroup(15), [13..15])(H);
        Print("Missing class |H|=", Size(H), ":\\n");
        Print("  proj [1..6]: ", proj1, " |proj|=", Size(proj1), "\\n");
        Print("  proj [7..12]: ", proj2, " |proj|=", Size(proj2), "\\n");
        Print("  proj [13..15]: ", proj3, " |proj|=", Size(proj3), "\\n");
        # Identify transitive group IDs
        for deg in [6, 6, 3] do
            # The projections should be transitive groups
        od;
        Print("  TransitiveIdentification: ");
        for orb_range in [[1..6], [7..12], [13..15]] do
            stab := Stabilizer(H, orb_range, OnSets);
            action := Action(H, orb_range);
            if NrMovedPoints(action) > 0 and IsTransitive(action) then
                tid := TransitiveIdentification(action);
                Print("T", Length(orb_range), "_", tid, " ");
            else
                Print("? ");
            fi;
        od;
        Print("\\n");
    od;
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_partition_compare.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_partition_compare.g"

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
        if any(kw in line for kw in ['Orbital', 'Difference', 'Missing', 'missing',
                                      'Missing class', 'proj', 'Total', '===',
                                      'Transitive', 'source']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
