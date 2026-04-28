"""
Debug test to trace through the actual lifting algorithm and see when orbital kicks in.
"""

import subprocess
import os
import sys

gap_commands = '''
# Debug test to trace through lifting

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("=================================================================\\n");
Print("DEBUG: Tracing lifting algorithm\\n");
Print("=================================================================\\n\\n");

# Create S3 x C2 x C2 x C2 manually
S3 := SymmetricGroup(3);
C2a := Group((4,5));
C2b := Group((6,7));
C2c := Group((8,9));

shifted := [S3, C2a, C2b, C2c];
offs := [0, 3, 5, 7];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

Print("|P| = ", Size(P), "\\n");
series := ChiefSeries(P);
Print("Chief series length: ", Length(series), "\\n\\n");

# Manually trace through lifting
current := [P];
Print("Starting with ", Length(current), " subgroup(s)\\n");

for i in [1..Length(series)-1] do
    M := series[i];
    N := series[i+1];
    layerSize := Size(M) / Size(N);

    Print("\\n=== Layer ", i, ": |M|=", Size(M), " -> |N|=", Size(N), " (factor ", layerSize, ") ===\\n");
    Print("Have ", Length(current), " subgroup(s) containing M\\n");

    # Check each S
    for j in [1..Length(current)] do
        S := current[j];
        Print("  S[", j, "]: |S| = ", Size(S), "\\n");

        # Compute outer normalizer
        N_S := Normalizer(P, S);
        N_M := Normalizer(P, M);
        outerNorm := Intersection(N_S, N_M);

        outerGens := [];
        for gen in GeneratorsOfGroup(outerNorm) do
            if not gen in S then
                Add(outerGens, gen);
            fi;
        od;

        Print("    |N_P(S)| = ", Size(N_S), ", |N_P(M)| = ", Size(N_M), "\\n");
        Print("    |N_P(S) intersect N_P(M)| = ", Size(outerNorm), "\\n");
        Print("    Outer gens (not in S): ", Length(outerGens), "\\n");

        # Check coprime condition
        if Gcd(Size(S)/Size(M), layerSize) = 1 then
            Print("    -> COPRIME (Schur-Zassenhaus applies)\\n");
        else
            Print("    -> NON-COPRIME (H^1 enumeration needed)\\n");
        fi;
    od;

    # Do the actual lift
    current := LiftThroughLayer(P, M, N, current, shifted, offs);
    Print("After lift: ", Length(current), " FPF subdirect(s)\\n");
od;

Print("\\n=================================================================\\n");
Print("Final: ", Length(current), " FPF subdirect products\\n");
Print("=================================================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_lifting_debug.g", "w", encoding='utf-8') as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_lifting_debug.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running lifting trace debug...")
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
    if stderr:
        # Only show non-warning errors
        errors = [line for line in stderr.split('\\n') if 'Syntax warning' not in line and line.strip()]
        if errors:
            print("\\nSTDERR (errors):")
            print('\\n'.join(errors))
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)

print("\\nDebug trace completed!")
