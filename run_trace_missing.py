"""
Trace the missing subgroups: find which layer's orbital merge causes the loss.

We know no_orb[15] and no_orb[18] (size 216) from combo [3,2],[6,5],[6,8]
are missing from the orbital results. We need to find which intermediate
layer's orbital reduction removes their "parent" complement.

Strategy:
1. Run without orbital, get the 26 results
2. Identify results 15 and 18
3. For each chief series layer (bottom-up), track which intermediate
   subgroup each of these results "came from"
4. Run with orbital at each layer individually, to find which layer
   causes the loss
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_missing.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Tracing missing subgroups ===\\n\\n");

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

Print("|P| = ", Size(P), "\\n");
Print("Chief series of P:\\n");
series := RefinedChiefSeries(P);
for i in [1..Length(series)] do
    Print("  ", i, ": |G| = ", Size(series[i]));
    if i > 1 then
        Print(" factor size = ", Size(series[i-1]) / Size(series[i]));
    fi;
    Print("\\n");
od;
Print("\\n");

# Run without orbital to get the full 26 results
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();

result_no_orb := FindFPFClassesByLifting(P, shifted, offs, N);
Print("No-orbital: ", Length(result_no_orb), " results\\n");

# Identify the missing ones (size 216)
missing := Filtered([1..Length(result_no_orb)], i -> Size(result_no_orb[i]) = 216);
Print("Size-216 results at indices: ", missing, "\\n");
Print("Total size-216: ", Length(missing), "\\n\\n");

# Now run with orbital at each layer INDIVIDUALLY
# to find which layer causes the loss.
# We do this by patching LiftThroughLayer to optionally
# enable/disable orbital per layer.

_OrigLiftThroughLayer := LiftThroughLayer;
ENABLE_ORBITAL_LAYER := -1;  # -1 = disable all, 0+ = enable only this layer

_layerNum := 0;

# Actually, a simpler approach: run orbital, and for each
# chief series layer, track which subgroups contain the "missing" ones.

Print("=== Layer-by-layer trace ===\\n");
numLayers := Length(series) - 1;
Print("Number of layers: ", numLayers, "\\n\\n");

# For each pair of consecutive layers in the non-orbital result,
# check which subgroups "contain" the missing results

# Re-run with orbital, but instrument to track at each layer
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();

# Manual layer-by-layer lifting
current_orb := [P];
current_no_orb := [P];

for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    layerSize := Size(M) / Size(NN);
    Print("\\n--- Layer ", layer_idx, ": factor size=", layerSize, " ---\\n");

    # Lift with orbital
    USE_H1_ORBITAL := true;
    ClearH1Cache();
    new_orb := LiftThroughLayer(P, M, NN, current_orb, shifted, offs, fail);
    Print("  orbital: ", Length(current_orb), " parents -> ", Length(new_orb), " children\\n");

    # Lift without orbital
    USE_H1_ORBITAL := false;
    ClearH1Cache();
    new_no_orb := LiftThroughLayer(P, M, NN, current_no_orb, shifted, offs, fail);
    Print("  no_orbital: ", Length(current_no_orb), " parents -> ", Length(new_no_orb), " children\\n");

    # Compare: how many no_orb children are NOT P-conjugate to any orb child?
    if Length(new_orb) < Length(new_no_orb) then
        Print("  DIFFERENCE: orbital has ", Length(new_no_orb) - Length(new_orb), " fewer!\\n");
    elif Length(new_orb) > Length(new_no_orb) then
        Print("  STRANGE: orbital has MORE!\\n");
    else
        Print("  Same count.\\n");
    fi;

    # Update
    current_orb := new_orb;
    current_no_orb := new_no_orb;

    if Length(current_orb) = 0 and Length(current_no_orb) = 0 then
        break;
    fi;
od;

Print("\\n=== Final results ===\\n");
Print("orbital: ", Length(current_orb), "\\n");
Print("no_orbital: ", Length(current_no_orb), "\\n");
Print("Difference: ", Length(current_no_orb) - Length(current_orb), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_missing.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_missing.g"

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
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    key_lines = [line for line in log.split('\n')
                 if 'Layer' in line or 'DIFFERENCE' in line or 'result' in line.lower()
                 or 'parents' in line or 'children' in line or 'Final' in line
                 or 'factor' in line or 'series' in line]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 2000 CHARS ===")
    print(log[-2000:])
except FileNotFoundError:
    print("Log file not found!")
