"""
Test script for verifying the orbital method fix on [3,2,2,2] partition.

This partition is a good test case because:
1. It has repeated factors (three 2s), which creates multiple complement classes
2. The outer normalizer N_P(S) ∩ N_P(M) should have elements outside S
3. We expect actual orbit reduction (not 0% like with inner automorphisms)
"""

import subprocess
import os
import sys

gap_commands = '''
# Test the orbital method fix on [3,2,2,2] partition

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("=================================================================\\n");
Print("Testing H^1 Orbital Method on [3,2,2,2] partition (n=9)\\n");
Print("=================================================================\\n\\n");

# Reset statistics
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

# Test [3,2,2,2] partition
partition := [3,2,2,2];
n := Sum(partition);
Print("Partition: ", partition, " (n=", n, ")\\n");

# Get transitive groups for each factor
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));

Print("Factor counts: ", List(transitiveLists, Length), "\\n\\n");

# Just test with S_k factors for simplicity
factors := List(partition, SymmetricGroup);
Print("Testing with symmetric group factors: ", List(factors, Size), "\\n");

# Build the direct product
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    # ShiftGroup is defined in lifting_algorithm.g
    if off = 0 then
        Add(shifted, factors[k]);
    else
        # Create shifted version manually
        gens := GeneratorsOfGroup(factors[k]);
        newGens := [];
        for g in gens do
            moved := MovedPoints(factors[k]);
            newPerm := [];
            for i in moved do
                img := i^g;
                Add(newPerm, [i + off, img + off]);
            od;
            Add(newGens, MappingPermListList(
                List(newPerm, x -> x[1]),
                List(newPerm, x -> x[2])
            ));
        od;
        if Length(newGens) = 0 then
            Add(shifted, Group(()));
        else
            Add(shifted, Group(newGens));
        fi;
    fi;
    off := off + NrMovedPoints(factors[k]);
od;

if Length(shifted) = 1 then
    P := shifted[1];
else
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
fi;

Print("|P| = ", Size(P), "\\n");
Print("Chief series length: ", Length(ChiefSeries(P)), "\\n\\n");

# Time the lifting algorithm
startTime := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
elapsedTime := Runtime() - startTime;

Print("\\n");
Print("Results:\\n");
Print("--------\\n");
Print("Found ", Length(result), " FPF subdirect products\\n");
Print("Time: ", Float(elapsedTime) / 1000.0, " seconds\\n\\n");

# Print H^1 timing stats
PrintH1TimingStats();

# Print orbital stats if available
if IsBound(PrintH1OrbitalStats) then
    PrintH1OrbitalStats();
fi;

# Verify by checking a few subdirects
Print("\\n");
Print("Verification:\\n");
Print("-------------\\n");
Print("Checking first few subdirects are valid FPF...\\n");
validCount := 0;
for i in [1..Minimum(5, Length(result))] do
    S := result[i];
    isValid := true;

    # Check each projection
    for j in [1..Length(shifted)] do
        factor := shifted[j];
        offset := offs[j];
        degree := NrMovedPoints(factor);
        moved := [offset+1..offset+degree];

        gens_proj := List(GeneratorsOfGroup(S), g -> RestrictedPerm(g, moved));
        gens_proj := Filtered(gens_proj, g -> g <> ());

        if Length(gens_proj) = 0 then
            isValid := false;
            break;
        fi;

        projection := Group(gens_proj);

        if Size(projection) <> Size(factor) then
            isValid := false;
            break;
        fi;

        if not IsTransitive(projection, moved) then
            isValid := false;
            break;
        fi;
    od;

    if isValid then
        validCount := validCount + 1;
        Print("  Subdirect ", i, ": |S| = ", Size(S), " - VALID\\n");
    else
        Print("  Subdirect ", i, ": |S| = ", Size(S), " - INVALID\\n");
    fi;
od;

Print("\\n");
if validCount = Minimum(5, Length(result)) then
    Print("All checked subdirects are valid!\\n");
else
    Print("WARNING: Some subdirects failed validation!\\n");
fi;

Print("\\n=================================================================\\n");
Print("Test complete.\\n");
Print("=================================================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_3222.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_3222.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running [3,2,2,2] orbital method test...")
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
    stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout
    print(stdout)
    if stderr:
        print("\nSTDERR:")
        print(stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out after 10 minutes")
    sys.exit(1)

# Check for errors
if process.returncode != 0:
    print(f"\nERROR: GAP exited with code {process.returncode}")
    sys.exit(1)

print("\nTest completed successfully!")
