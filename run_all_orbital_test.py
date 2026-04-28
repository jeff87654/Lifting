"""
Test orbital at all layers simultaneously.
Also test combinations of layers.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/all_orbital_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Multi-Layer Orbital Test ===\\n\\n");

# Build the combo
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
T63_2 := TransitiveGroup(3, 2);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

series := RefinedChiefSeries(P);
numLayers := Length(series) - 1;
Print("Chief series: ", List(series, Size), "\\n");
Print("Factor sizes: ", List([1..numLayers], i -> Size(series[i])/Size(series[i+1])), "\\n\\n");

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

# Baseline: all no-orbital
USE_H1_ORBITAL := false;
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("Baseline (no orbital): ", Length(current), " results\\n");
base_dedup := DedupUnderN(current, N);
Print("  N-classes: ", Length(base_dedup), "\\n\\n");

# All orbital
USE_H1_ORBITAL := true;
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("All orbital: ", Length(current), " results\\n");
all_dedup := DedupUnderN(current, N);
Print("  N-classes: ", Length(all_dedup), "\\n\\n");

# Check which baseline classes are missing
if Length(all_dedup) < Length(base_dedup) then
    Print("Missing classes:\\n");
    for i in [1..Length(base_dedup)] do
        found := false;
        for j in [1..Length(all_dedup)] do
            if Size(base_dedup[i]) = Size(all_dedup[j]) then
                if RepresentativeAction(N, base_dedup[i], all_dedup[j]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Print("  base_class[", i, "]: |H|=", Size(base_dedup[i]), "\\n");
        fi;
    od;
fi;

# Test orbital at layers 4+8 together (the two layers that have orbital merges)
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    if layer_idx = 4 or layer_idx = 8 then
        USE_H1_ORBITAL := true;
    else
        USE_H1_ORBITAL := false;
    fi;
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("Orbital at 4+8: ", Length(current), " results\\n");
dedup_48 := DedupUnderN(current, N);
Print("  N-classes: ", Length(dedup_48), "\\n\\n");

# Test orbital ONLY at layer 4
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    if layer_idx = 4 then
        USE_H1_ORBITAL := true;
    else
        USE_H1_ORBITAL := false;
    fi;
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("Orbital ONLY at 4: ", Length(current), " results\\n");
dedup_4 := DedupUnderN(current, N);
Print("  N-classes: ", Length(dedup_4), "\\n\\n");

# Test orbital ONLY at layer 8
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    if layer_idx = 8 then
        USE_H1_ORBITAL := true;
    else
        USE_H1_ORBITAL := false;
    fi;
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("Orbital ONLY at 8: ", Length(current), " results\\n");
dedup_8 := DedupUnderN(current, N);
Print("  N-classes: ", Length(dedup_8), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_all_orbital.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_all_orbital.g"

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
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    key_lines = [line for line in log.split('\n')
                 if any(kw in line for kw in ['Baseline', 'orbital', 'N-classes', 'Missing',
                                               'results', 'Chief', 'Factor'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 2000 CHARS ===")
    print(log[-2000:])
except FileNotFoundError:
    print("Log file not found!")
