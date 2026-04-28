"""
Diagnose orbital undercounting for [6,6,3] partition.
Compare orbital ON vs OFF results and identify which specific classes differ.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_diagnosis.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# We need to find which specific combo in [6,6,3] produces the discrepancy.
# We'll test each combo in [6,6,3] separately.

USE_H1_ORBITAL := true;
CHECKPOINT_DIR := fail;

# Get the transitive groups for the partition [6,6,3]
trans6 := List([1..NrTransitiveGroups(6)], i -> TransitiveGroup(6, i));
trans3 := List([1..NrTransitiveGroups(3)], i -> TransitiveGroup(3, i));

Print("Transitive groups: ", NrTransitiveGroups(6), " for deg 6, ",
      NrTransitiveGroups(3), " for deg 3\\n");

# Enumerate all combos [T6_i, T6_j, T3_k] with i <= j (since partition is [6,6,3])
combos := [];
for i in [1..NrTransitiveGroups(6)] do
    for j in [i..NrTransitiveGroups(6)] do
        for k in [1..NrTransitiveGroups(3)] do
            Add(combos, [i, j, k]);
        od;
    od;
od;
Print("Total combos to test: ", Length(combos), "\\n\\n");

# For each combo, run with orbital ON and OFF, compare counts
discrepancies := [];
for idx in [1..Length(combos)] do
    combo := combos[idx];
    i := combo[1]; j := combo[2]; k := combo[3];

    factors := [TransitiveGroup(6, i), TransitiveGroup(6, j), TransitiveGroup(3, k)];
    shifted := [];
    offs := [];
    off := 0;
    for kk in [1..3] do
        Add(offs, off);
        Add(shifted, ShiftGroup(factors[kk], off));
        off := off + NrMovedPoints(factors[kk]);
    od;
    N := BuildConjugacyTestGroup(15, [6, 6, 3]);

    # Check if it could be FPF subdirect
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    if not IsFPFSubdirect(P, shifted, offs) then
        continue;
    fi;

    # Test 1: Orbital ON
    P1 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    USE_H1_ORBITAL := true;
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();
    r1 := FindFPFClassesByLifting(P1, shifted, offs, N);
    count_on := Length(r1);

    # Test 2: Orbital OFF
    P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    USE_H1_ORBITAL := false;
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();
    r2 := FindFPFClassesByLifting(P2, shifted, offs, N);
    count_off := Length(r2);

    if count_on <> count_off then
        Print("*** DISCREPANCY [T6_", i, ", T6_", j, ", T3_", k, "]: ",
              "orbital ON=", count_on, " OFF=", count_off,
              " diff=", count_off - count_on, "\\n");
        Add(discrepancies, rec(combo := combo, on := count_on, off := count_off));
    fi;
od;

Print("\\n=== Summary ===\\n");
Print("Total discrepancies: ", Length(discrepancies), "\\n");
total_diff := 0;
for d in discrepancies do
    total_diff := total_diff + (d.off - d.on);
    Print("  [T6_", d.combo[1], ", T6_", d.combo[2], ", T3_", d.combo[3], "]: ",
          "ON=", d.on, " OFF=", d.off, " diff=", d.off - d.on, "\\n");
od;
Print("Total difference: ", total_diff, "\\n");
Print("Expected difference: 2 (for [6,6,3])\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_orbital_diagnosis.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_orbital_diagnosis.g"

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
        if any(kw in line for kw in ['DISCREPANCY', 'Summary', 'Total', 'Expected', 'diff']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
