"""
Trace the missing class from [6,6,3] orbital computation.

The missing class has |H| = 216 with orbits [6, 6, 3].
First identify which combo it comes from, then trace per-layer.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_missing2.log"

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

Print("Missing class |H| = ", Size(H_missing), "\\n");
Print("StructureDescription: ", StructureDescription(H_missing), "\\n");

# Determine the transitive groups on each block
r1 := Action(H_missing, [1..6]);
r2 := Action(H_missing, [7..12]);
r3 := Action(H_missing, [13..15]);
Print("Block 1: T(6,", TransitiveIdentification(r1), ") order=", Size(r1), "\\n");
Print("Block 2: T(6,", TransitiveIdentification(r2), ") order=", Size(r2), "\\n");
Print("Block 3: T(3,", TransitiveIdentification(r3), ") order=", Size(r3), "\\n");

tid1 := TransitiveIdentification(r1);
tid2 := TransitiveIdentification(r2);
tid3 := TransitiveIdentification(r3);

Print("\\nThe missing class comes from combo involving T(6,", tid1, ") x T(6,", tid2, ") x T(3,", tid3, ")\\n");

# Set up the combo
factors := [TransitiveGroup(6, tid1), TransitiveGroup(6, tid2), TransitiveGroup(3, tid3)];
Print("Factor orders: ", List(factors, Size), "\\n");
Print("|P| = ", Product(List(factors, Size)), "\\n");

shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Verify H_missing is in P
if IsSubgroup(P, H_missing) then
    Print("H_missing IS in P - confirmed combo!\\n");
else
    Print("H_missing is NOT in P\\n");
    # Try with swapped factors
    factors2 := [TransitiveGroup(6, tid2), TransitiveGroup(6, tid1), TransitiveGroup(3, tid3)];
    shifted2 := [];
    offs2 := [];
    off := 0;
    for k in [1..3] do
        Add(offs2, off);
        Add(shifted2, ShiftGroup(factors2[k], off));
        off := off + NrMovedPoints(factors2[k]);
    od;
    P2 := Group(Concatenation(List(shifted2, GeneratorsOfGroup)));
    if IsSubgroup(P2, H_missing) then
        Print("H_missing IS in P2 (swapped factors)\\n");
        P := P2;
        shifted := shifted2;
        offs := offs2;
        factors := factors2;
    else
        # Try conjugation
        for g in GeneratorsOfGroup(N) do
            if IsSubgroup(P, H_missing^g) then
                Print("H_missing^g IS in P for some g in N\\n");
                H_missing := H_missing^g;
                break;
            fi;
        od;
    fi;
fi;

# Chief series
series := RefinedChiefSeries(P);
Print("\\nChief series: ", List(series, Size), "\\n");
Print("Layer factors: ");
for i in [1..Length(series)-1] do
    Print(Size(series[i])/Size(series[i+1]), " ");
od;
Print("\\n\\n");

# Layer-by-layer comparison
Print("=== Layer-by-layer trace (orbital ON vs OFF) ===\\n\\n");

parents_off := [P];
parents_on := [P];

for layerIdx in [1..Length(series)-1] do
    M_cur := series[layerIdx];
    L_cur := series[layerIdx + 1];
    layerSize := Size(M_cur) / Size(L_cur);

    Print("--- Layer ", layerIdx, ": |M|=", Size(M_cur), " -> |L|=", Size(L_cur),
          " (factor size=", layerSize, ") ---\\n");

    # OFF
    USE_H1_ORBITAL := false;
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents_off_new := LiftThroughLayer(P, M_cur, L_cur, parents_off, shifted, offs, fail);

    # ON
    USE_H1_ORBITAL := true;
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents_on_new := LiftThroughLayer(P, M_cur, L_cur, parents_on, shifted, offs, fail);

    Print("  OFF: ", Length(parents_off), " -> ", Length(parents_off_new),
          ", ON: ", Length(parents_on), " -> ", Length(parents_on_new), "\\n");

    diff := Length(parents_off_new) - Length(parents_on_new);
    if diff <> 0 then
        Print("  *** LAYER DIFF = ", diff, " ***\\n");

        # Find which parents from OFF are missing from ON
        missingParents := [];
        for j in [1..Length(parents_off_new)] do
            S_off := parents_off_new[j];
            found_in_on := false;
            # First try exact equality
            for k in [1..Length(parents_on_new)] do
                if S_off = parents_on_new[k] then
                    found_in_on := true;
                    break;
                fi;
            od;
            if not found_in_on then
                # Try P-conjugacy
                for k in [1..Length(parents_on_new)] do
                    if Size(S_off) = Size(parents_on_new[k]) then
                        if RepresentativeAction(P, S_off, parents_on_new[k]) <> fail then
                            found_in_on := true;
                            break;
                        fi;
                    fi;
                od;
            fi;
            if not found_in_on then
                Add(missingParents, j);
            fi;
        od;

        Print("  Missing parents from ON: ", Length(missingParents), " of ", Length(parents_off_new), "\\n");
        for j in missingParents do
            Print("    Missing #", j, ": |S|=", Size(parents_off_new[j]),
                  " StructDesc=", StructureDescription(parents_off_new[j]), "\\n");
        od;
    fi;

    parents_off := parents_off_new;
    parents_on := parents_on_new;
od;

Print("\\n=== Final ===\\n");
Print("OFF: ", Length(parents_off), ", ON: ", Length(parents_on), "\\n");
Print("Diff: ", Length(parents_off) - Length(parents_on), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_missing2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_missing2.g"

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
        if any(kw in line for kw in ['Missing', 'missing', 'Block', 'combo', 'confirmed',
                                      'Structure', '===', 'Total', 'OFF', 'ON',
                                      'Found', 'NOT', 'DIFF', 'Layer', '---',
                                      'parent', 'Gens', 'factor', 'Difference',
                                      'T(', '|P|', '|H|', 'Chief', 'NOT in',
                                      'swapped', 'Final', 'Diff']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
