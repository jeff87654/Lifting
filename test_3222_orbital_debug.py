"""
Debug test for orbital method - add verbose output to understand why orbital isn't being used.
"""

import subprocess
import os
import sys

gap_commands = '''
# Debug test for orbital method

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("=================================================================\\n");
Print("DEBUG: Testing orbital method call path\\n");
Print("=================================================================\\n\\n");

# Test a simple case directly
# Create S3 x C2 x C2 x C2 manually
S3 := SymmetricGroup(3);
C2a := Group((4,5));
C2b := Group((6,7));
C2c := Group((8,9));

P := Group(Concatenation(
    GeneratorsOfGroup(S3),
    GeneratorsOfGroup(C2a),
    GeneratorsOfGroup(C2b),
    GeneratorsOfGroup(C2c)
));

Print("|P| = ", Size(P), "\\n");
Print("Chief series: ", ChiefSeries(P), "\\n");

# Let's look at a specific layer where we might use H^1
# The chief series of this product should have some elementary abelian layers

series := ChiefSeries(P);
Print("\\nChief series layers:\\n");
for i in [1..Length(series)-1] do
    M := series[i];
    N := series[i+1];
    Print("  Layer ", i, ": |M| = ", Size(M), ", |N| = ", Size(N), ", |M/N| = ", Size(M)/Size(N), "\\n");
od;

# Now let's manually test the outer normalizer computation
Print("\\n=== Testing outer normalizer computation ===\\n");

# Take a specific S (P itself) and layer M -> N
S := P;
M := series[1];  # The full group P
N := series[2];  # First proper normal subgroup

Print("S = P, M = series[1], N = series[2]\\n");
Print("|M| = ", Size(M), ", |N| = ", Size(N), "\\n");

# Compute normalizers
N_S := Normalizer(P, S);
N_M := Normalizer(P, M);
Print("N_P(S) = ", Size(N_S), " (should be P since S=P)\\n");
Print("N_P(M) = ", Size(N_M), " (should be P since M=P)\\n");

outerNorm := Intersection(N_S, N_M);
Print("N_P(S) intersection N_P(M) = ", Size(outerNorm), "\\n");

outerGens := [];
for gen in GeneratorsOfGroup(outerNorm) do
    if not gen in S then
        Add(outerGens, gen);
    fi;
od;
Print("Generators outside S: ", Length(outerGens), "\\n\\n");

# Try a deeper layer
if Length(series) >= 3 then
    Print("=== Trying deeper layers ===\\n");
    for layerIdx in [2..Minimum(4, Length(series)-1)] do
        M2 := series[layerIdx];
        N2 := series[layerIdx+1];
        Print("Layer ", layerIdx, ": M = series[", layerIdx, "], N = series[", layerIdx+1, "]\\n");
        Print("  |M| = ", Size(M2), ", |N| = ", Size(N2), ", |M/N| = ", Size(M2)/Size(N2), "\\n");

        # For this layer, S could be any subgroup containing M2
        # Let's use S = P
        N_S2 := Normalizer(P, P);
        N_M2 := Normalizer(P, M2);
        outerNorm2 := Intersection(N_S2, N_M2);
        Print("  N_P(P) intersection N_P(M) = ", Size(outerNorm2), "\\n");

        outerGens2 := [];
        for gen in GeneratorsOfGroup(outerNorm2) do
            if not gen in P then
                Add(outerGens2, gen);
            fi;
        od;
        Print("  Outer generators (outside P): ", Length(outerGens2), "\\n");

        # What about inside P but outside M2?
        insideGens := [];
        for gen in GeneratorsOfGroup(outerNorm2) do
            if gen in P and not gen in M2 then
                Add(insideGens, gen);
            fi;
        od;
        Print("  Generators in P but outside M: ", Length(insideGens), "\\n\\n");
    od;
fi;

# Key insight: the outer normalizer elements need to be in P but OUTSIDE S
# If S = P (which it often is at the start), then there are no outer elements!
# This is why orbital method isn't being called.

Print("\\n=== Key Insight ===\\n");
Print("When S = P (the full ambient), N_P(S) intersect N_P(M) = P and all generators\\n");
Print("are IN S, so there are no outer normalizer generators.\\n");
Print("\\n");
Print("The orbital method only helps when S is a PROPER subgroup of P,\\n");
Print("meaning we're lifting through a layer after descending from P.\\n");
Print("\\n");
Print("For [3,2,2,2], most layers are handled by coprime (Schur-Zassenhaus)\\n");
Print("since S3 has order 6 and the C2 factors are coprime or small.\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_orbital.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_orbital.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running debug test...")
print("=" * 65)

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=120)
    print(stdout)
    if stderr and "Syntax warning" not in stderr:
        print("\nSTDERR (errors only):")
        for line in stderr.split('\n'):
            if 'Syntax warning' not in line and line.strip():
                print(line)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)

print("\nDebug test completed!")
