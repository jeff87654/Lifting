"""
Debug: Check what outer normalizer elements actually look like
"""

import subprocess
import os
import sys

gap_commands = '''
# Debug: examine outer normalizer elements

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Examining outer normalizer elements ===\\n\\n");

# Create S3 x C2 x C2 x C2
S3 := SymmetricGroup(3);  # Acts on {1,2,3}
C2a := Group((4,5));      # Acts on {4,5}
C2b := Group((6,7));      # Acts on {6,7}
C2c := Group((8,9));      # Acts on {8,9}

P := Group(Concatenation(
    GeneratorsOfGroup(S3),
    GeneratorsOfGroup(C2a),
    GeneratorsOfGroup(C2b),
    GeneratorsOfGroup(C2c)
));

Print("P generators: ", GeneratorsOfGroup(P), "\\n");
Print("Moved points of P: ", MovedPoints(P), "\\n\\n");

series := ChiefSeries(P);

# Look at layer 3 where we had outer gens
M := series[3];
Print("M = series[3], |M| = ", Size(M), "\\n");
Print("M generators: ", GeneratorsOfGroup(M), "\\n");
Print("Moved points of M: ", MovedPoints(M), "\\n\\n");

# Get a proper subgroup S of P that contains M
# After lifting, we'll have subgroups like this
# For now, let's construct one manually

# Find complements to series[1]/series[2] in series[1]/series[3]
# Actually, let's just take a maximal subgroup of P that contains M
maxSubs := MaximalSubgroupClassReps(P);
Print("Maximal subgroups of P: ", Length(maxSubs), "\\n");

for i in [1..Length(maxSubs)] do
    S := maxSubs[i];
    if IsSubset(S, M) then
        Print("\\nMaximal subgroup ", i, ": |S| = ", Size(S), " contains M\\n");
        Print("S generators: ", GeneratorsOfGroup(S), "\\n");
        Print("Moved points of S: ", MovedPoints(S), "\\n");

        # Compute outer normalizer
        N_S := Normalizer(P, S);
        N_M := Normalizer(P, M);
        outerNorm := Intersection(N_S, N_M);

        Print("N_P(S) = ", Size(N_S), ", N_P(M) = ", Size(N_M), "\\n");
        Print("N_P(S) intersect N_P(M) = ", Size(outerNorm), "\\n");

        outerGens := [];
        for gen in GeneratorsOfGroup(outerNorm) do
            if not gen in S then
                Add(outerGens, gen);
            fi;
        od;

        Print("Outer gens (not in S): ", Length(outerGens), "\\n");
        for gen in outerGens do
            Print("  ", gen, " - moves points ", MovedPoints(Group(gen)), "\\n");
            # Check if gen normalizes S trivially (i.e., acts as identity on S)
            # by checking if conjugation by gen fixes every element of S
            trivialAction := true;
            for s in GeneratorsOfGroup(S) do
                if s^gen <> s then
                    trivialAction := false;
                    break;
                fi;
            od;
            if trivialAction then
                Print("    -> Acts TRIVIALLY on S (centralizes S)\\n");
            else
                Print("    -> Non-trivial action on S\\n");
            fi;
        od;
    fi;
od;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_outer_norm.g", "w", encoding='utf-8') as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_outer_norm.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running outer normalizer examination...")
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
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)

print("\nExamination completed!")
