"""
Find partitions where the orbital method could provide speedups.

We're looking for cases where N_P(S) intersect N_P(M) has elements
outside S that DON'T centralize S.
"""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("=================================================================\\n");
Print("Searching for partitions with non-trivial outer action on H^1\\n");
Print("=================================================================\\n\\n");

# Function to check if there are non-centralizing outer normalizers
CheckPartitionForOuterAction := function(partition)
    local n, factors, shifted, offs, off, k, P, gens, newGens, g, moved, i, img,
          series, layerIdx, M, N, S, subgroups, maxSubs, found,
          N_S, N_M, outerNorm, gen, hasCases, caseCount;

    n := Sum(partition);
    factors := List(partition, SymmetricGroup);

    # Build shifted product
    shifted := [];
    offs := [];
    off := 0;
    for k in [1..Length(factors)] do
        Add(offs, off);
        if off = 0 then
            Add(shifted, factors[k]);
        else
            gens := GeneratorsOfGroup(factors[k]);
            newGens := [];
            for g in gens do
                moved := MovedPoints(factors[k]);
                Add(newGens, MappingPermListList(
                    List(moved, x -> x + off),
                    List(moved, x -> x^g + off)
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

    series := ChiefSeries(P);
    hasCases := false;
    caseCount := 0;

    # Get some FPF subdirects via lifting
    subgroups := [P];
    for layerIdx in [1..Minimum(3, Length(series)-1)] do
        M := series[layerIdx];
        N := series[layerIdx+1];

        # Lift through layer
        subgroups := LiftThroughLayer(P, M, N, subgroups, shifted, offs);

        # Check each S for non-centralizing outer normalizers
        for S in subgroups do
            if S = P then continue; fi;  # Skip full group

            N_S := Normalizer(P, S);
            N_M := Normalizer(P, M);
            outerNorm := Intersection(N_S, N_M);

            for gen in GeneratorsOfGroup(outerNorm) do
                if not gen in S then
                    # Check if gen centralizes S
                    if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                        # Found a non-centralizing outer element!
                        if not hasCases then
                            Print("Partition ", partition, " (n=", n, "):\\n");
                            hasCases := true;
                        fi;
                        caseCount := caseCount + 1;
                        Print("  Layer ", layerIdx, ": |S|=", Size(S), ", found non-centralizing outer gen\\n");
                        Print("    gen = ", gen, "\\n");
                        Print("    |N_P(S) int N_P(M)| = ", Size(outerNorm), "\\n");
                        break;  # One example per S is enough
                    fi;
                fi;
            od;
        od;

        if caseCount > 3 then break; fi;  # Limit output
    od;

    return hasCases;
end;

# Test various partition types
Print("=== Testing partitions with repeated factors ===\\n\\n");

# [k, k] type
for k in [2..4] do
    if 2*k <= 10 then
        CheckPartitionForOuterAction([k, k]);
    fi;
od;

Print("\\n=== Testing partitions with many small factors ===\\n\\n");

# [2, 2, ...] type
for numTwos in [3..5] do
    part := ListWithIdenticalEntries(numTwos, 2);
    if Sum(part) <= 10 then
        CheckPartitionForOuterAction(part);
    fi;
od;

Print("\\n=== Testing mixed partitions ===\\n\\n");

# Mixed types
CheckPartitionForOuterAction([4, 4]);
CheckPartitionForOuterAction([3, 3, 2]);
CheckPartitionForOuterAction([4, 2, 2]);
CheckPartitionForOuterAction([3, 3, 3]);
CheckPartitionForOuterAction([5, 5]);

Print("\\n=== Checking [k,k] more deeply ===\\n\\n");

# For [k, k], look at diagonal-type subdirects specifically
CheckDiagonalSubdirects := function(k)
    local Sk, P, shifted, offs, diag, diagGens, g, gen1, gen2,
          N_diag, outerGens, gen, hasCases;

    Print("Checking [", k, ",", k, "] diagonal structure:\\n");

    Sk := SymmetricGroup(k);
    # Shifted copy
    gen1 := GeneratorsOfGroup(Sk);
    gen2 := List(gen1, g -> MappingPermListList(
        List(MovedPoints(Sk), x -> x + k),
        List(MovedPoints(Sk), x -> x^g + k)
    ));

    P := Group(Concatenation(gen1, gen2));
    shifted := [Sk, Group(gen2)];
    offs := [0, k];

    # Construct diagonal subgroup {(g, g) : g in Sk}
    diagGens := [];
    for g in gen1 do
        Add(diagGens, g * MappingPermListList(
            List(MovedPoints(Sk), x -> x + k),
            List(MovedPoints(Sk), x -> x^g + k)
        ));
    od;
    diag := Group(diagGens);

    Print("  |Diagonal| = ", Size(diag), "\\n");
    Print("  Diagonal gens: ", diagGens, "\\n");

    # Check normalizer
    N_diag := Normalizer(P, diag);
    Print("  |N_P(Diag)| = ", Size(N_diag), "\\n");

    outerGens := [];
    hasCases := false;
    for gen in GeneratorsOfGroup(N_diag) do
        if not gen in diag then
            if not ForAll(GeneratorsOfGroup(diag), s -> s^gen = s) then
                Add(outerGens, gen);
                hasCases := true;
            fi;
        fi;
    od;

    if hasCases then
        Print("  FOUND non-centralizing outer gens: ", Length(outerGens), "\\n");
        for gen in outerGens do
            Print("    ", gen, "\\n");
        od;
    else
        Print("  No non-centralizing outer elements found\\n");
    fi;

    Print("\\n");
    return hasCases;
end;

for k in [3..5] do
    CheckDiagonalSubdirects(k);
od;

Print("\\n=================================================================\\n");
Print("Search complete.\\n");
Print("=================================================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_find_orbital.g", "w", encoding='utf-8') as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_find_orbital.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Searching for partitions with non-trivial outer action...")
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
    stdout, stderr = process.communicate(timeout=300)
    print(stdout)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Search timed out")
    sys.exit(1)

print("\nSearch completed!")
