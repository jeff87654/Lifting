"""
Test orbital method on [3,3] partition where we found non-centralizing outer elements.
"""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("=================================================================\\n");
Print("Testing orbital method on [3,3] partition\\n");
Print("=================================================================\\n\\n");

# Reset stats
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

partition := [3,3];
n := Sum(partition);
Print("Partition: ", partition, " (n=", n, ")\\n\\n");

# Build the product
S3 := SymmetricGroup(3);
gen1 := GeneratorsOfGroup(S3);
gen2 := List(gen1, g -> MappingPermListList(
    List(MovedPoints(S3), x -> x + 3),
    List(MovedPoints(S3), x -> x^g + 3)
));

P := Group(Concatenation(gen1, gen2));
shifted := [S3, Group(gen2)];
offs := [0, 3];

Print("|P| = ", Size(P), "\\n");
Print("Chief series length: ", Length(ChiefSeries(P)), "\\n\\n");

# Run lifting
startTime := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
elapsedTime := Runtime() - startTime;

Print("\\n");
Print("Results:\\n");
Print("--------\\n");
Print("Found ", Length(result), " FPF subdirect products\\n");
Print("Time: ", Float(elapsedTime) / 1000.0, " seconds\\n\\n");

# Print stats
PrintH1TimingStats();
if IsBound(PrintH1OrbitalStats) then
    PrintH1OrbitalStats();
fi;

# Verify count with full enumeration for small case
Print("\\nVerification via full enumeration:\\n");
allSubs := List(ConjugacyClassesSubgroups(P), Representative);
fpfCount := 0;
for S in allSubs do
    isFPF := true;
    for i in [1..Length(shifted)] do
        factor := shifted[i];
        offset := offs[i];
        degree := NrMovedPoints(factor);
        moved := [offset+1..offset+degree];

        gens_proj := List(GeneratorsOfGroup(S), g -> RestrictedPerm(g, moved));
        gens_proj := Filtered(gens_proj, g -> g <> ());

        if Length(gens_proj) = 0 then
            isFPF := false;
            break;
        fi;

        projection := Group(gens_proj);

        if Size(projection) <> Size(factor) then
            isFPF := false;
            break;
        fi;

        if not IsTransitive(projection, moved) then
            isFPF := false;
            break;
        fi;
    od;
    if isFPF then
        fpfCount := fpfCount + 1;
    fi;
od;

Print("Full enumeration found: ", fpfCount, " FPF subdirects\\n");
if fpfCount = Length(result) then
    Print("MATCH - Lifting result is correct!\\n");
else
    Print("MISMATCH - Lifting: ", Length(result), ", Full: ", fpfCount, "\\n");
fi;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_33.g", "w", encoding='utf-8') as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_33.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing [3,3] partition...")
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

print("\nTest completed!")
