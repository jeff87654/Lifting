"""
Investigate Layer 4 of combo [3,2],[6,5],[6,8] in detail.

Layer 4: factor size=3 (C_3 chief factor)
- With orbital: 3 -> 2 orbits -> 1 FPF
- Without orbital: 2 parents, 4 children (meaning 2 FPF from this specific parent)

We manually step through the chief series to Layer 4 and inspect:
1. What are the 3 complements?
2. What is the H^1 action matrix?
3. Which complements pass FPF?
4. Which complements are in the same orbit?
5. Are the two FPF-passing complements actually P-conjugate?
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_layer4.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Layer 4 Investigation ===\\n\\n");

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

series := RefinedChiefSeries(P);
Print("Chief series lengths: ", List(series, Size), "\\n\\n");

# Step through layers 1-3 WITHOUT orbital to get the 2 parents for Layer 4
USE_H1_ORBITAL := false;
ClearH1Cache();

current := [P];
for layer_idx in [1..3] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
    Print("After layer ", layer_idx, ": ", Length(current), " subgroups\\n");
od;

Print("\\nParents for Layer 4: ", Length(current), " subgroups\\n");
for i in [1..Length(current)] do
    Print("  Parent[", i, "]: |S| = ", Size(current[i]), "\\n");
od;

# Now manually process Layer 4
M := series[4];
NN := series[5];
layerSize := Size(M) / Size(NN);
Print("\\nLayer 4: M=", Size(M), " N=", Size(NN), " factor=", layerSize, "\\n");

# For each parent, compute complements with and without orbital
for parent_idx in [1..Length(current)] do
    S := current[parent_idx];
    Print("\\n=== Parent ", parent_idx, ": |S| = ", Size(S), " ===\\n");

    # Find L values
    normalsBetween := NormalSubgroupsBetween(S, M, NN);
    Print("Normals between: ", Length(normalsBetween), "\\n");

    for L in normalsBetween do
        if Size(L) = Size(M) then continue; fi;

        hom := NaturalHomomorphismByNormalSubgroup(S, L);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("\\n  L: |L| = ", Size(L), " |Q| = ", Size(Q), " |M_bar| = ", Size(M_bar), "\\n");

        if not IsElementaryAbelian(M_bar) or Size(M_bar) = 1 then
            Print("  Skipping (not elementary abelian or trivial)\\n");
            continue;
        fi;

        # Create module and compute H^1
        ClearH1Cache();
        module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
        if not IsRecord(module) or IsBound(module.isNonSplit) then
            Print("  Non-split extension\\n");
            continue;
        fi;

        H1 := CachedComputeH1(module);
        Print("  H^1 dim = ", H1.H1Dimension, " p = ", module.p, "\\n");

        if H1.H1Dimension = 0 then
            Print("  Unique complement\\n");
            continue;
        fi;

        # Get ALL complement classes
        complementInfo := BuildComplementInfo(Q, M_bar, module);
        allComplements := EnumerateComplementsFromH1(H1, complementInfo);
        Print("  All complement classes: ", Length(allComplements), "\\n");

        # FPF filter
        fpfFilter := function(C_bar)
            local C_lifted;
            C_lifted := PreImages(hom, C_bar);
            return IsFPFSubdirect(C_lifted, shifted, offs);
        end;

        fpfResults := Filtered(allComplements, fpfFilter);
        Print("  FPF-passing complements: ", Length(fpfResults), "\\n");

        for i in [1..Length(allComplements)] do
            isFPF := fpfFilter(allComplements[i]);
            Print("    Complement ", i, ": |C| = ", Size(allComplements[i]), " FPF = ", isFPF, "\\n");
        od;

        # Compute outer normalizer
        N_S := Normalizer(P, S);
        N_M := Normalizer(P, M);
        outerNorm := Intersection(N_S, N_M);
        Print("\\n  |N_P(S)| = ", Size(N_S), " |N_P(M)| = ", Size(N_M));
        Print(" |outerNorm| = ", Size(outerNorm), "\\n");

        outerNormGens := [];
        for gen in GeneratorsOfGroup(outerNorm) do
            if not gen in S then
                if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                    Add(outerNormGens, gen);
                fi;
            fi;
        od;
        Print("  Outer norm gens outside S: ", Length(outerNormGens), "\\n");

        if Length(outerNormGens) > 0 then
            # Filter for L-normalization
            if Size(L) > 1 then
                outerNormGens := Filtered(outerNormGens,
                    gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));
                Print("  After L-normalization filter: ", Length(outerNormGens), "\\n");
            fi;
        fi;

        if Length(outerNormGens) > 0 then
            # Compute action matrices
            for i in [1..Length(outerNormGens)] do
                ClearH1Cache();
                module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
                H1 := CachedComputeH1(module);
                mat := ComputeOuterActionOnH1(H1, module, outerNormGens[i], S, L, hom, P);
                Print("  Action matrix[", i, "] = ", mat, "\\n");
            od;

            # Run orbital method
            ClearH1Cache();
            orbResult := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, hom, P, fpfFilter);
            Print("\\n  Orbital result: ", Length(orbResult), " FPF complements\\n");

            # Compare
            if Length(orbResult) < Length(fpfResults) then
                Print("\\n  *** MISMATCH: orbital=", Length(orbResult), " all_fpf=", Length(fpfResults), " ***\\n");

                # Check P-conjugacy between FPF complements
                Print("\\n  Checking P-conjugacy of FPF complements...\\n");
                for i in [1..Length(fpfResults)] do
                    for j in [i+1..Length(fpfResults)] do
                        # Lift back to S and check P-conjugacy
                        C_i := PreImages(hom, fpfResults[i]);
                        C_j := PreImages(hom, fpfResults[j]);
                        isConj := RepresentativeAction(P, C_i, C_j);
                        Print("  FPF[", i, "] vs FPF[", j, "]: P-conjugate? ", isConj <> fail, "\\n");
                    od;
                od;

                # Also check which orbit each FPF complement is in
                Print("\\n  H^1 coordinates of each complement:\\n");
                ClearH1Cache();
                module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
                H1 := CachedComputeH1(module);
                complementInfo := BuildComplementInfo(Q, M_bar, module);

                for i in [1..Length(allComplements)] do
                    # Find the cocycle for this complement
                    # This is tricky - we need to reverse-engineer from the complement
                    Print("  Complement ", i, ": ");
                    Print("|C|=", Size(allComplements[i]), " FPF=", fpfFilter(allComplements[i]));
                    Print("\\n");
                od;
            fi;
        else
            Print("  No outer norm gens - orbital won't merge\\n");
        fi;
    od;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_layer4.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_layer4.g"

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

    print("\n=== FULL LOG ===")
    print(log)
except FileNotFoundError:
    print("Log file not found!")
