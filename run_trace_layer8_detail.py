"""
Detailed investigation of Layer 8 orbital bug.

Layer 8: factor size=3, last layer of chief series.
With orbital only at layer 8: 26 -> 21 results, 13 N-classes (should be 14).
Missing base_reps[11]: |H|=216.

For each parent at layer 8, compare orbital vs no-orbital complements.
When orbital merges complements, check if the merged ones are truly N-conjugate.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_layer8_detail.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Layer 8 Detail ===\\n\\n");

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

series := RefinedChiefSeries(P);
numLayers := Length(series) - 1;

# Lift through layers 1-7 WITHOUT orbital to get parents for layer 8
USE_H1_ORBITAL := false;
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers-1] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;
Print("Parents for layer 8: ", Length(current), "\\n");
for i in [1..Length(current)] do
    Print("  Parent[", i, "]: |S| = ", Size(current[i]), "\\n");
od;

# Layer 8 parameters
M := series[numLayers];
NN := series[numLayers + 1];
layerSize := Size(M) / Size(NN);
Print("\\nLayer 8: M=", Size(M), " N=", Size(NN), " factor=", layerSize, "\\n\\n");

# Process each parent manually
all_orb := [];
all_no_orb := [];

for parent_idx in [1..Length(current)] do
    S := current[parent_idx];
    Print("=== Parent ", parent_idx, ": |S| = ", Size(S), " ===\\n");

    normalsBetween := NormalSubgroupsBetween(S, M, NN);
    Print("  Normals between: ", Length(normalsBetween), "\\n");

    for L in normalsBetween do
        if Size(L) = Size(M) then continue; fi;

        hom := NaturalHomomorphismByNormalSubgroup(S, L);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("  L: |L|=", Size(L), " |Q|=", Size(Q), " |M_bar|=", Size(M_bar), "\\n");

        if not IsElementaryAbelian(M_bar) or Size(M_bar) = 1 then
            Print("    Skipping\\n");
            continue;
        fi;

        # WITHOUT orbital: get all complements + FPF filter
        ClearH1Cache();
        module_no := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
        if not IsRecord(module_no) or IsBound(module_no.isNonSplit) then
            Print("    Non-split\\n");
            continue;
        fi;
        H1_no := CachedComputeH1(module_no);
        if H1_no.H1Dimension = 0 then
            # unique complement
            complInfo_no := BuildComplementInfo(Q, M_bar, module_no);
            compl_no_orb := EnumerateComplementsFromH1(H1_no, complInfo_no);
            Print("    H1 dim=0, unique complement\\n");
        else
            complInfo_no := BuildComplementInfo(Q, M_bar, module_no);
            compl_no_orb := EnumerateComplementsFromH1(H1_no, complInfo_no);
            Print("    H1 dim=", H1_no.H1Dimension, " p=", module_no.p, " all=", Length(compl_no_orb), "\\n");
        fi;

        # FPF filter
        fpfFilter := function(C_bar)
            local C_lifted;
            C_lifted := PreImages(hom, C_bar);
            return IsFPFSubdirect(C_lifted, shifted, offs);
        end;

        fpf_no_orb := Filtered(compl_no_orb, fpfFilter);
        Print("    FPF (no orbital): ", Length(fpf_no_orb), "\\n");

        # Lift FPF complements
        for C_bar in fpf_no_orb do
            Add(all_no_orb, PreImages(hom, C_bar));
        od;

        # WITH orbital
        if H1_no.H1Dimension > 0 then
            # Compute outer normalizer
            N_S := Normalizer(P, S);
            N_M := Normalizer(P, M);
            outerNorm := Intersection(N_S, N_M);

            outerNormGens := [];
            for gen in GeneratorsOfGroup(outerNorm) do
                if not gen in S then
                    if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                        Add(outerNormGens, gen);
                    fi;
                fi;
            od;

            # L-normalization filter
            if Size(L) > 1 then
                outerNormGens := Filtered(outerNormGens,
                    gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));
            fi;

            Print("    Outer norm gens: ", Length(outerNormGens), "\\n");

            if Length(outerNormGens) > 0 then
                ClearH1Cache();
                orb_result := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, hom, P, fpfFilter);
                Print("    Orbital FPF: ", Length(orb_result), "\\n");

                for C_bar in orb_result do
                    Add(all_orb, PreImages(hom, C_bar));
                od;

                # COMPARE: which no_orb complements are missing from orb?
                if Length(orb_result) < Length(fpf_no_orb) then
                    Print("    *** ORBITAL DROPS ", Length(fpf_no_orb) - Length(orb_result), " FPF COMPLEMENT(S) ***\\n");

                    # For each FPF no_orb complement, check if it's P-conjugate to an orb one
                    for i in [1..Length(fpf_no_orb)] do
                        found := false;
                        for j in [1..Length(orb_result)] do
                            if RepresentativeAction(Q, fpf_no_orb[i], orb_result[j]) <> fail then
                                found := true;
                                break;
                            fi;
                        od;
                        if not found then
                            Print("      fpf_no[", i, "]: NOT P-conjugate to any orbital result\\n");

                            # Check if it's in the same H^1 orbit
                            # Get H^1 coordinates
                            Print("      |fpf_no[", i, "]| = ", Size(fpf_no_orb[i]), "\\n");
                        fi;
                    od;

                    # Check N-conjugacy of the lifted versions
                    Print("    Checking N-conjugacy of lifted FPF complements...\\n");
                    for i in [1..Length(fpf_no_orb)] do
                        C_i := PreImages(hom, fpf_no_orb[i]);
                        found_N := false;
                        for j in [1..Length(orb_result)] do
                            C_j := PreImages(hom, orb_result[j]);
                            if RepresentativeAction(N, C_i, C_j) <> fail then
                                found_N := true;
                                break;
                            fi;
                        od;
                        if not found_N then
                            Print("      Lifted fpf_no[", i, "]: NOT N-conjugate to any orbital. |H|=", Size(C_i), "\\n");
                        else
                            Print("      Lifted fpf_no[", i, "]: N-conjugate to orbital. |H|=", Size(C_i), "\\n");
                        fi;
                    od;

                    # Verify: are the dropped complements in the SAME H^1 orbit?
                    Print("    H^1 orbit analysis:\\n");
                    ClearH1Cache();
                    module2 := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
                    H1_2 := CachedComputeH1(module2);
                    Print("      H1 dim=", H1_2.H1Dimension, "\\n");

                    # Compute action record
                    action_rec := BuildH1ActionRecord(H1_2, module2, outerNormGens);
                    if action_rec <> fail then
                        Print("      Action matrices: ", action_rec.matrices, "\\n");
                        # Compute orbits
                        orbits := ComputeH1OrbitsExplicit(action_rec);
                        Print("      Number of orbits: ", Length(orbits), "\\n");
                        for k in [1..Length(orbits)] do
                            Print("        Orbit ", k, ": size ", Length(orbits[k]), " reps: ", orbits[k], "\\n");
                        od;
                    fi;
                fi;
            else
                # No outer norm gens - orbital won't merge
                for C_bar in fpf_no_orb do
                    Add(all_orb, PreImages(hom, C_bar));
                od;
            fi;
        else
            # H1 dim=0, same as no orbital
            for C_bar in fpf_no_orb do
                Add(all_orb, PreImages(hom, C_bar));
            od;
        fi;
    od;
od;

Print("\\n=== Summary ===\\n");
Print("all_orb: ", Length(all_orb), "\\n");
Print("all_no_orb: ", Length(all_no_orb), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_layer8_detail.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_layer8_detail.g"

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

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    # Extract key lines
    key_lines = [line for line in log.split('\n')
                 if any(kw in line for kw in ['Parent', 'FPF', 'orbital', 'DROPS',
                                               'NOT', 'Missing', 'N-conjug',
                                               'orbit', 'matrices', 'Summary',
                                               'dim=', 'Outer'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 3000 CHARS ===")
    print(log[-3000:])
except FileNotFoundError:
    print("Log file not found!")
