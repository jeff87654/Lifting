"""
Test whether PreImagesRepresentative(hom_P, gi_Q) returns elements in S vs P.
This is the suspected cause of incorrect orbital action computation.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/hom_preimage_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Reconstruct the [6,6,3] combo [T66_5, T66_8, T63_2]
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

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := TrivialSubgroup(P);  # Bottom of chief series

# Get the chief series
series := RefinedChiefSeries(P);
Print("Chief series lengths: ", List(series, Size), "\\n");

# Find the last non-trivial layer (layer 8)
M := series[Length(series) - 1];
Print("M = series[", Length(series)-1, "] with |M| = ", Size(M), "\\n");
Print("N = series[", Length(series), "] with |N| = ", Size(N), "\\n");

# Do lifting through layers 1 to 7 to get the 17 parents at layer 8
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

parents := [P];
for i in [1..Length(series)-2] do
    ClearH1Cache();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
Print("Parents at final layer: ", Length(parents), "\\n");

# Now for each parent, check the hom_P vs per-parent hom behavior
M_final := series[Length(series) - 1];  # M at the final layer
N_final := series[Length(series)];      # N at the final layer (trivial)

Print("\\n=== Checking hom_P preimage test ===\\n");
Print("M_final = ", M_final, " |M_final| = ", Size(M_final), "\\n");
Print("N_final = ", N_final, " |N_final| = ", Size(N_final), "\\n");

# Check if hom_P would be used (|P/N| <= 200 and > 10 parents)
Print("Size(P)/Size(N_final) = ", Size(P)/Size(N_final), "\\n");
Print("Number of parents = ", Length(parents), "\\n");

if Size(N_final) > 1 and Size(P)/Size(N_final) <= 200 then
    hom_P := NaturalHomomorphismByNormalSubgroup(P, N_final);
    Print("hom_P would be ACTIVE\\n");
else
    Print("hom_P would be INACTIVE (N_final is trivial)\\n");
    # For trivial N, L = N is the bottom, so L = trivial group
    # Then hom = NaturalHomomorphismByNormalSubgroup(S, L) = S -> S/1 = S
    # So hom_P won't help here
fi;

# The final layer has N = trivial, so L = N = trivial
# Let's check what the hom situation is for the PRECEDING layers
Print("\\n=== Checking layers where hom_P might activate ===\\n");
for layerIdx in [1..Length(series)-1] do
    M_layer := series[layerIdx];
    N_layer := series[layerIdx + 1];
    layer_size := Size(M_layer) / Size(N_layer);
    ratio := Size(P) / Size(N_layer);
    would_active := Size(N_layer) > 1 and ratio <= 200;
    Print("Layer ", layerIdx, ": |M|=", Size(M_layer), " |N|=", Size(N_layer),
          " |M/N|=", layer_size, " |P/N|=", ratio,
          " hom_P=", would_active, "\\n");
od;

# For the SECOND-TO-LAST layer where the 17 vs 14 divergence happens:
# Let's manually reproduce the lifting of the last layer for ONE parent
# and compare hom_P vs fresh hom behavior

Print("\\n=== Detailed test for one parent in the last layer ===\\n");
S := parents[1];
L := N_final;  # trivial
M := M_final;

# Fresh hom
hom_fresh := NaturalHomomorphismByNormalSubgroup(S, L);
Q_fresh := ImagesSource(hom_fresh);
M_bar_fresh := Image(hom_fresh, M);

# Module via fresh hom
module_fresh := ChiefFactorAsModule(Q_fresh, M_bar_fresh, TrivialSubgroup(M_bar_fresh));
Print("Fresh module type: ", RecNames(module_fresh), "\\n");
if IsBound(module_fresh.preimageGens) then
    Print("Fresh preimageGens count: ", Length(module_fresh.preimageGens), "\\n");
    for i in [1..Length(module_fresh.preimageGens)] do
        gi := module_fresh.preimageGens[i];
        preimg := PreImagesRepresentative(hom_fresh, gi);
        Print("  gen ", i, ": gi=", gi, " preimage=", preimg,
              " preimage in S? ", preimg in S, "\\n");
    od;
fi;

# Since N is trivial, hom_P guard fails (Size(N) > 1 required)
# So hom_P is NEVER used for the last layer with trivial N!
# This means the last layer always uses fresh per-parent hom.
# The bug must be in an EARLIER layer.

Print("\\n=== Key insight: hom_P only activates for non-trivial N ===\\n");
Print("For the last layer (N=trivial), hom_P is NEVER used.\\n");
Print("Checking which layers have non-trivial N AND many parents:\\n");

# The bug affects 17 parents after layer 7, so let's check layer 7
# Layer 7: series[7] -> series[8]
M7 := series[7];
N7 := series[8];
Print("\\nLayer 7: |M|=", Size(M7), " |N|=", Size(N7),
      " |P/N|=", Size(P)/Size(N7), "\\n");
if Size(N7) > 1 and Size(P)/Size(N7) <= 200 then
    Print("  hom_P would be ACTIVE for layer 7\\n");
    # Check with the ACTUAL parents going into layer 7
    # We need to trace through the layers to find them
fi;

# Actually, let's trace from the START and print hom_P activation at each layer
Print("\\n=== Full trace with actual parent counts ===\\n");
trace_parents := [P];
for i in [1..Length(series)-1] do
    M_i := series[i];
    N_i := series[i+1];
    np := Length(trace_parents);
    ratio := Size(P)/Size(N_i);
    hom_p_active := Size(N_i) > 1 and ratio <= 200 and np > 10;
    Print("Layer ", i, ": ", np, " parents, |M/N|=", Size(M_i)/Size(N_i),
          " |P/N|=", ratio, " hom_P=", hom_p_active, "\\n");
    ClearH1Cache();
    trace_parents := LiftThroughLayer(P, M_i, N_i, trace_parents, shifted, offs, fail);
    Print("  -> ", Length(trace_parents), " results\\n");
od;
Print("Final: ", Length(trace_parents), " results\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_hom_preimage_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_hom_preimage_test.g"

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

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(kw in line for kw in ['Layer', 'hom_P', 'parents', 'Parent', 'preimage',
                                  'insight', 'trace', 'ACTIVE', 'INACTIVE',
                                  'Chief', 'Final', 'results', 'Detailed',
                                  'Key', 'module', 'gen ']):
        print(line.strip())
