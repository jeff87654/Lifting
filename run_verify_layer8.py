"""
Verify Layer 8 orbital correctness for combo T(6,5) x T(6,8) x T(3,2).

For each parent at Layer 8, verify that orbit members are truly P-conjugate.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/verify_layer8.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Set up combo
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
numLayers := Length(series) - 1;

# First, build the correct parent set for Layer 8 using ALL orbital OFF
Print("Building parents through layers 1-7 with orbital OFF...\\n");
USE_H1_ORBITAL := false;
parents := [P];
for i in [1..numLayers - 1] do
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
Print("Layer 8 parents (OFF): ", Length(parents), "\\n\\n");

# Now analyze Layer 8 in detail
M := series[numLayers];
L := series[numLayers + 1];
Print("Layer 8: |M|=", Size(M), " -> |L|=", Size(L), " (factor=", Size(M)/Size(L), ")\\n\\n");

# For EACH parent, check orbital correctness
for idx in [1..Length(parents)] do
    S := parents[idx];
    hom := NaturalHomomorphismByNormalSubgroup(S, L);
    Q := ImagesSource(hom);
    M_bar := Image(hom, M);

    if not IsElementaryAbelian(M_bar) or Size(M_bar) = 1 then
        continue;
    fi;

    # Get ALL complements (no orbital)
    ClearH1Cache();
    all_complements := ComplementClassesRepresentatives(Q, M_bar);

    if Length(all_complements) <= 1 then
        continue;
    fi;

    # Check FPF for each
    fpf_indices := [];
    for i in [1..Length(all_complements)] do
        C_lifted := PreImages(hom, all_complements[i]);
        if IsFPFSubdirect(C_lifted, shifted, offs) then
            Add(fpf_indices, i);
        fi;
    od;

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
    outerNormGens := Filtered(outerNormGens,
        gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));

    if Length(outerNormGens) = 0 then
        continue;
    fi;

    # Compute H^1 orbital
    ClearH1Cache();
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    if not IsRecord(module) or (IsBound(module.isNonSplit) and module.isNonSplit) then
        continue;
    fi;
    if IsBound(module.isModuleConstructionFailed) and module.isModuleConstructionFailed then
        continue;
    fi;

    H1 := CachedComputeH1(module);

    if H1.H1Dimension = 0 then
        continue;
    fi;

    H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, hom, P);

    if H1action = fail or Length(H1action.matrices) = 0 then
        continue;
    fi;

    # Compute orbits
    orbitReps := ComputeH1Orbits(H1action);
    complementInfo := BuildComplementInfo(Q, M_bar, module);

    Print("Parent ", idx, ": |S|=", Size(S), " |Q|=", Size(Q),
          " complements=", Length(all_complements),
          " FPF=", Length(fpf_indices),
          " H1dim=", H1.H1Dimension,
          " orbits=", Length(orbitReps),
          " outerGens=", Length(outerNormGens),
          "\\n");

    # For EACH action matrix, verify: v -> v*mat means their complements are P-conjugate
    bugFound := false;
    for matIdx in [1..Length(H1action.matrices)] do
        mat := H1action.matrices[matIdx];
        for rep in H1.H1Representatives do
            neighbor := rep * mat;
            if neighbor <> rep then
                cocycle1 := H1CoordsToFullCocycle(H1, rep);
                cocycle2 := H1CoordsToFullCocycle(H1, neighbor);
                C1 := CocycleToComplement(cocycle1, complementInfo);
                C2 := CocycleToComplement(cocycle2, complementInfo);
                C1_lift := PreImages(hom, C1);
                C2_lift := PreImages(hom, C2);

                conj := RepresentativeAction(P, C1_lift, C2_lift);
                if conj = fail then
                    Print("  *** BUG at parent ", idx, " mat ", matIdx,
                          ": ", rep, " -> ", neighbor,
                          " NOT P-conjugate! ***\\n");
                    Print("    |C1|=", Size(C1_lift), " |C2|=", Size(C2_lift), "\\n");
                    Print("    C1 FPF=", IsFPFSubdirect(C1_lift, shifted, offs),
                          " C2 FPF=", IsFPFSubdirect(C2_lift, shifted, offs), "\\n");
                    bugFound := true;
                fi;
            fi;
        od;
    od;

    if not bugFound then
        Print("  All orbit merges verified P-conjugate.\\n");
    fi;
od;

Print("\\nDone.\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_verify_layer8.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_layer8.g"

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

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Parent', 'BUG', 'verified', 'orbital', 'Done',
                                      'Building', 'Layer', 'parents']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
