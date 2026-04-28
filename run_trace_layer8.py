"""
Test orbital at each layer independently.

For each layer i, run orbital ONLY at that layer (no-orbital for all others).
Compare with fully no-orbital to find which single layer's orbital causes the loss.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_layer8.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Per-Layer Orbital Test ===\\n\\n");

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

Print("|P| = ", Size(P), " |N| = ", Size(N), "\\n");

series := RefinedChiefSeries(P);
numLayers := Length(series) - 1;
Print("Number of layers: ", numLayers, "\\n\\n");

# First: full no-orbital baseline
USE_H1_ORBITAL := false;
ClearH1Cache();
current_base := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    current_base := LiftThroughLayer(P, M, NN, current_base, shifted, offs, fail);
od;
Print("Baseline (all no-orbital): ", Length(current_base), " results\\n\\n");

# For each layer, enable orbital ONLY at that layer
for target_layer in [1..numLayers] do
    current := [P];
    for layer_idx in [1..numLayers] do
        M := series[layer_idx];
        NN := series[layer_idx + 1];
        ClearH1Cache();
        if layer_idx = target_layer then
            USE_H1_ORBITAL := true;
        else
            USE_H1_ORBITAL := false;
        fi;
        current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
    od;
    diff := Length(current_base) - Length(current);
    if diff <> 0 then
        Print("Orbital ONLY at layer ", target_layer, ": ", Length(current), " results (diff=", diff, ")\\n");

        # Check N-conjugacy
        DedupUnderN := function(results, N_group)
            local reps, H, found, i;
            reps := [];
            for H in results do
                found := false;
                for i in [1..Length(reps)] do
                    if RepresentativeAction(N_group, H, reps[i]) <> fail then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    Add(reps, H);
                fi;
            od;
            return reps;
        end;

        reps := DedupUnderN(current, N);
        base_reps := DedupUnderN(current_base, N);
        Print("  N-classes: orbital_at_", target_layer, "=", Length(reps), " baseline=", Length(base_reps), "\\n");

        if Length(reps) < Length(base_reps) then
            Print("  *** LOSS OF N-CLASS! ***\\n");

            # Find which baseline class is missing
            for i in [1..Length(base_reps)] do
                found := false;
                for j in [1..Length(reps)] do
                    if RepresentativeAction(N, base_reps[i], reps[j]) <> fail then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    Print("  Missing base_reps[", i, "]: |H|=", Size(base_reps[i]), "\\n");
                fi;
            od;
        fi;
    else
        Print("Orbital ONLY at layer ", target_layer, ": ", Length(current), " results (same)\\n");
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_layer8.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_layer8.g"

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

    # Extract key lines
    key_lines = [line for line in log.split('\n')
                 if any(kw in line for kw in ['Orbital ONLY', 'Baseline', 'LOSS', 'Missing',
                                               'N-classes', 'diff=', 'results'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 2000 CHARS ===")
    print(log[-2000:])
except FileNotFoundError:
    print("Log file not found!")
