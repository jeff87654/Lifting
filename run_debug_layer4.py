"""
Debug Layer 4 of combo T(6,5) x T(6,8) x T(3,2) where orbital loses 1 complement.

Layer 4: |M|=216 -> |L|=72, factor=3
Parent count: 2
OFF: 2 -> 4 children
ON: 2 -> 3 children (H^1 orbital: 3 -> 2 orbits -> 1 FPF)

The orbital method merges 3 H^1 elements into 2 orbits, selects 1 FPF.
But the correct answer has 2 FPF complements that are NOT P-conjugate.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/debug_layer4.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Set up the combo T(6,5) x T(6,8) x T(3,2)
factors := [TransitiveGroup(6, 5), TransitiveGroup(6, 8), TransitiveGroup(3, 2)];
shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

series := RefinedChiefSeries(P);
Print("Chief series sizes: ", List(series, Size), "\\n");
Print("Layer factors: ");
for i in [1..Length(series)-1] do
    Print(Size(series[i])/Size(series[i+1]), " ");
od;
Print("\\n\\n");

# Lift through layers 1-3 to get to Layer 4's parents
# Use orbital OFF (correct) to get the right parents
USE_H1_ORBITAL := false;
ClearH1Cache();
FPF_SUBDIRECT_CACHE := rec();

parents := [P];
for i in [1..3] do
    M_cur := series[i];
    L_cur := series[i + 1];
    parents := LiftThroughLayer(P, M_cur, L_cur, parents, shifted, offs, fail);
    Print("After layer ", i, ": ", Length(parents), " parents (sizes: ", List(parents, Size), ")\\n");
od;

Print("\\n=== Layer 4 Analysis: |M|=216 -> |L|=72 (factor=3) ===\\n");
M := series[4];
L := series[5];
Print("|M| = ", Size(M), ", |L| = ", Size(L), "\\n");
Print("M/L is C_3, M is: ", StructureDescription(M), "\\n");
Print("L is: ", StructureDescription(L), "\\n");

Print("\\nParents for Layer 4: ", Length(parents), "\\n");
for idx in [1..Length(parents)] do
    S := parents[idx];
    Print("  Parent ", idx, ": |S|=", Size(S), " StructDesc=", StructureDescription(S), "\\n");
od;

# For EACH parent, compare orbital ON vs OFF complements
for idx in [1..Length(parents)] do
    S := parents[idx];
    Print("\\n======== Parent ", idx, " (|S|=", Size(S), ") ========\\n");

    # Form quotient S/L
    hom := NaturalHomomorphismByNormalSubgroup(S, L);
    Q := ImagesSource(hom);
    M_bar := Image(hom, M);
    Print("Q = S/L: |Q|=", Size(Q), ", |M_bar|=", Size(M_bar), "\\n");
    Print("G = Q/M_bar: |G|=", Size(Q)/Size(M_bar), "\\n");

    # Get ALL complements (no orbital)
    ClearH1Cache();
    all_complements := ComplementClassesRepresentatives(Q, M_bar);
    Print("All complement classes: ", Length(all_complements), "\\n");

    # Check FPF for each
    fpf_complements := [];
    for i in [1..Length(all_complements)] do
        C_bar := all_complements[i];
        C_lifted := PreImages(hom, C_bar);
        if IsFPFSubdirect(C_lifted, shifted, offs) then
            Add(fpf_complements, C_bar);
            Print("  Complement ", i, ": FPF=YES, |C|=", Size(C_bar), "\\n");
        else
            Print("  Complement ", i, ": FPF=NO, |C|=", Size(C_bar), "\\n");
        fi;
    od;
    Print("FPF complements: ", Length(fpf_complements), "\\n");

    # Check P-conjugacy of FPF complements
    if Length(fpf_complements) > 1 then
        Print("\\n--- P-conjugacy check of FPF complements ---\\n");
        for i in [1..Length(fpf_complements)] do
            for j in [i+1..Length(fpf_complements)] do
                C1 := fpf_complements[i];
                C2 := fpf_complements[j];
                # Lift to S and check P-conjugacy
                C1_lift := PreImages(hom, C1);
                C2_lift := PreImages(hom, C2);
                conj_elt := RepresentativeAction(P, C1_lift, C2_lift);
                if conj_elt <> fail then
                    Print("  FPF[", i, "] ~ FPF[", j, "] (P-conjugate by ", conj_elt, ")\\n");
                else
                    Print("  FPF[", i, "] NOT ~ FPF[", j, "] (NOT P-conjugate!)\\n");
                fi;
            od;
        od;
    fi;

    # Now check what the orbital method does
    if Length(all_complements) > 1 and IsElementaryAbelian(M_bar) then
        Print("\\n--- Orbital method analysis ---\\n");

        # Compute outer normalizer
        N_S := Normalizer(P, S);
        N_M := Normalizer(P, M);
        outerNorm := Intersection(N_S, N_M);
        Print("N_P(S) = |", Size(N_S), "|, N_P(M) = |", Size(N_M), "|\\n");
        Print("outerNorm = N_P(S) cap N_P(M): |", Size(outerNorm), "|\\n");

        outerNormGens := [];
        for gen in GeneratorsOfGroup(outerNorm) do
            if not gen in S then
                if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                    Add(outerNormGens, gen);
                fi;
            fi;
        od;
        Print("Outer norm gens (outside S, non-centralizing): ", Length(outerNormGens), "\\n");

        # Filter for L-normalization
        outerNormGens := Filtered(outerNormGens,
            gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));
        Print("After L-normalization filter: ", Length(outerNormGens), "\\n");

        if Length(outerNormGens) > 0 then
            Print("Outer norm gen orders: ", List(outerNormGens, Order), "\\n");

            # Compute the H^1 orbital method result
            ClearH1Cache();
            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            H1 := CachedComputeH1(module);
            Print("H^1 dimension: ", H1.H1Dimension, "\\n");
            Print("Num complements (H^1 representatives): ", H1.numComplements, "\\n");

            # Compute action matrix
            H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, hom, P);
            if H1action <> fail then
                Print("Action matrices: ", Length(H1action.matrices), "\\n");
                for i in [1..Length(H1action.matrices)] do
                    Print("  Matrix ", i, ": ", H1action.matrices[i], "\\n");
                od;

                # Compute orbits
                orbitReps := ComputeH1Orbits(H1action);
                Print("Orbits: ", Length(orbitReps), " (from ", H1.numComplements, " points)\\n");

                # Show orbit structure
                Print("Orbit representatives: ", orbitReps, "\\n");

                # Build all complements and show their H^1 coordinates + FPF status
                complementInfo := BuildComplementInfo(Q, M_bar, module);
                Print("\\nAll H^1 vectors and their FPF status:\\n");
                for rep in H1.H1Representatives do
                    cocycleVec := H1CoordsToFullCocycle(H1, rep);
                    C := CocycleToComplement(cocycleVec, complementInfo);
                    C_lifted := PreImages(hom, C);
                    isFPF := IsFPFSubdirect(C_lifted, shifted, offs);
                    Print("  H^1 coord=", rep, " -> FPF=", isFPF, " |C|=", Size(C), "\\n");
                od;

                # For each orbit, check if the orbit rep is FPF
                # and whether all elements in the orbit have the same FPF status
                Print("\\nOrbit -> FPF mapping:\\n");
                for i in [1..Length(orbitReps)] do
                    rep := orbitReps[i];
                    cocycleVec := H1CoordsToFullCocycle(H1, rep);
                    C := CocycleToComplement(cocycleVec, complementInfo);
                    C_lifted := PreImages(hom, C);
                    isFPF := IsFPFSubdirect(C_lifted, shifted, offs);
                    Print("  Orbit ", i, ": rep=", rep, " FPF=", isFPF, "\\n");
                od;

                # CRITICAL: Verify orbit correctness
                # For each pair of H^1 vectors in the same orbit,
                # check if their complements are ACTUALLY P-conjugate
                Print("\\nVerifying P-conjugacy of orbit members:\\n");
                for mat in H1action.matrices do
                    for rep in H1.H1Representatives do
                        neighbor := rep * mat;
                        if neighbor <> rep then
                            # rep and neighbor should be P-conjugate
                            cocycle1 := H1CoordsToFullCocycle(H1, rep);
                            cocycle2 := H1CoordsToFullCocycle(H1, neighbor);
                            C1 := CocycleToComplement(cocycle1, complementInfo);
                            C2 := CocycleToComplement(cocycle2, complementInfo);
                            C1_lift := PreImages(hom, C1);
                            C2_lift := PreImages(hom, C2);
                            conj := RepresentativeAction(P, C1_lift, C2_lift);
                            if conj = fail then
                                Print("  *** BUG: ", rep, " -> ", neighbor,
                                      " are in same orbit but NOT P-conjugate! ***\\n");
                            else
                                Print("  OK: ", rep, " -> ", neighbor,
                                      " are P-conjugate\\n");
                            fi;
                        fi;
                    od;
                od;
            else
                Print("BuildH1ActionRecordFromOuterNorm returned fail!\\n");
            fi;
        else
            Print("No outer norm gens after filtering.\\n");
        fi;
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_layer4.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_layer4.g"

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

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    # Print all meaningful lines
    for line in log.split('\n'):
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith('Syntax warning') and not line_stripped.startswith('^'):
            if any(kw in line for kw in ['Parent', 'FPF', 'orbital', 'Orbital', 'Action',
                                          'Matrix', 'Orbit', 'orbit', 'conjugate', 'BUG',
                                          'OK:', 'H^1', 'dim', 'complement', 'Complement',
                                          'outer', 'Outer', 'coord', 'gen', 'Chief',
                                          'Layer', '===', '---', 'After layer',
                                          'Norm', 'norm', 'filter', 'Missing',
                                          'P-conj', 'NOT', 'rep=']):
                print(line_stripped)
except FileNotFoundError:
    print("Log file not found!")
