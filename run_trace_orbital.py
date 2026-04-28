"""
Deep trace of orbital bug for simplest case: [T6_2, T6_2, T3_1]
ON=3, OFF=4, diff=1.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_orbital.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# [T6_2, T6_2, T3_1]
T62 := TransitiveGroup(6, 2);
T31 := TransitiveGroup(3, 1);
factors := [T62, T62, T31];
shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
N := BuildConjugacyTestGroup(15, [6, 6, 3]);
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

# Get chief series
series := RefinedChiefSeries(P);
Print("Chief series: ", List(series, Size), "\\n");

# Lift through all but last layer
parents := [P];
for i in [1..Length(series)-2] do
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
Print("Parents at final layer: ", Length(parents), "\\n");

M := series[Length(series)-1];
L := series[Length(series)];  # trivial
Print("Final layer: |M|=", Size(M), " |L|=", Size(L), "\\n\\n");

# For each parent, manually compute complements both ways
for pidx in [1..Length(parents)] do
    S := parents[pidx];
    hom := NaturalHomomorphismByNormalSubgroup(S, L);
    Q := ImagesSource(hom);
    M_bar := Image(hom, M);

    Print("=== Parent ", pidx, " |S|=", Size(S), " |Q|=", Size(Q), " ===\\n");

    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    ClearH1Cache();
    H1 := CachedComputeH1(module);
    Print("  H1 dim = ", H1.H1Dimension, " numCompl = ", H1.numComplements, "\\n");

    if H1.H1Dimension > 0 then
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
        Print("  outerNormGens outside S: ", Length(outerNormGens), "\\n");

        if Length(outerNormGens) > 0 then
            # Compute action matrices on H1
            H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, hom, P);
            if H1action <> fail then
                Print("  Action matrices: ", H1action.matrices, "\\n");
                orbits := ComputeH1Orbits(H1action);
                Print("  Orbits: ", Length(orbits), " reps\\n");
                Print("  Orbit reps: ", orbits, "\\n");
            else
                Print("  H1 action failed\\n");
            fi;
        fi;

        # Compute ALL complements (orbital OFF)
        complementInfo := BuildComplementInfo(Q, M_bar, module);
        allComplements := EnumerateComplementsFromH1(H1, complementInfo);
        Print("  All complements: ", Length(allComplements), "\\n");

        # Check FPF for each
        fpfAll := [];
        for C_bar in allComplements do
            C_lifted := PreImages(hom, C_bar);
            if IsFPFSubdirect(C_lifted, shifted, offs) then
                Add(fpfAll, C_bar);
            fi;
        od;
        Print("  FPF complements (orbital OFF): ", Length(fpfAll), "\\n");

        # Compute orbit rep complements (orbital ON)
        if Length(outerNormGens) > 0 and H1action <> fail then
            orbitComplements := [];
            for rep in orbits do
                cocycleVec := H1CoordsToFullCocycle(H1, rep);
                C := CocycleToComplement(cocycleVec, complementInfo);
                if Size(C) * Size(M_bar) = Size(Q) and Size(Intersection(C, M_bar)) = 1 then
                    Add(orbitComplements, C);
                fi;
            od;
            Print("  Orbit rep complements: ", Length(orbitComplements), "\\n");

            # Check FPF for orbit reps
            fpfOrbital := [];
            for C_bar in orbitComplements do
                C_lifted := PreImages(hom, C_bar);
                if IsFPFSubdirect(C_lifted, shifted, offs) then
                    Add(fpfOrbital, C_bar);
                fi;
            od;
            Print("  FPF orbit reps (orbital ON): ", Length(fpfOrbital), "\\n");

            # Check: are the FPF-all complements truly non-conjugate under P?
            # Group them by P-conjugacy
            Print("\\n  Checking P-conjugacy of FPF complements:\\n");
            reps := [];
            for C_bar in fpfAll do
                C_lifted := PreImages(hom, C_bar);
                found := false;
                for j in [1..Length(reps)] do
                    if RepresentativeAction(P, C_lifted, reps[j]) <> fail then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    Add(reps, C_lifted);
                fi;
            od;
            Print("  P-conjugacy classes among FPF complements: ", Length(reps), "\\n");

            # Also check N-conjugacy
            repsN := [];
            for C_bar in fpfAll do
                C_lifted := PreImages(hom, C_bar);
                found := false;
                for j in [1..Length(repsN)] do
                    if RepresentativeAction(N, C_lifted, repsN[j]) <> fail then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    Add(repsN, C_lifted);
                fi;
            od;
            Print("  N-conjugacy classes among FPF complements: ", Length(repsN), "\\n");

            # Now check: which FPF complements from ALL list are NOT covered by orbital reps?
            Print("\\n  Checking coverage:\\n");
            for ci in [1..Length(fpfAll)] do
                C_bar_all := fpfAll[ci];
                C_lifted_all := PreImages(hom, C_bar_all);
                covered := false;
                for oi in [1..Length(fpfOrbital)] do
                    C_lifted_orb := PreImages(hom, fpfOrbital[oi]);
                    if RepresentativeAction(P, C_lifted_all, C_lifted_orb) <> fail then
                        covered := true;
                        break;
                    fi;
                od;
                if not covered then
                    Print("    FPF complement ", ci, " NOT covered by any orbital rep!\\n");
                    Print("    |C_lifted|=", Size(C_lifted_all), "\\n");
                fi;
            od;
        fi;
    fi;
    Print("\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_orbital.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_orbital.g"

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

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Parent', 'H1 dim', 'outerNorm', 'Action',
                                      'Orbit', 'complement', 'FPF', 'conjugacy',
                                      'covered', 'NOT covered', 'Chief', 'Final',
                                      'Parents', '===']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
