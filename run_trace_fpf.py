"""
Trace FPF status of ALL H^1 orbit reps (all complements in all orbits).
Compare between Size(P) and fresh P cases.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_fpf.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

Print("\\n=== Trace FPF of all H^1 complements ===\\n\\n");

TraceLifting := function(P, label)
    local series, M, NN, hom, Q, M_bar, L, normalsBetween,
          complements, C_bar, C, fpf_status, i, j, h1_result,
          S, outerNormGens, N_S, outerNorm, gen, cachedNormPM,
          hom_P, M_bar_P, module, H1, complementInfo, cocycleVec,
          allH1, orbitReps, numOrbits, fullCount;

    series := RefinedChiefSeries(P);
    Print(label, ": Chief series sizes = ", List(series, Size), "\\n");

    # We need layer 8 (that's where the difference is)
    # But let's trace ALL layers
    local current, layer_idx;
    current := [P];

    for layer_idx in [1..Length(series)-1] do
        M := series[layer_idx];
        NN := series[layer_idx + 1];

        # Only trace layers with H^1 orbital activity
        # Just use LiftThroughLayer for non-interesting layers
        if layer_idx <> 4 and layer_idx <> 8 then
            USE_H1_ORBITAL := true;
            ClearH1Cache();
            current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
            Print(label, " Layer ", layer_idx, ": ", Length(current), " results\\n");
            continue;
        fi;

        Print("\\n", label, " Layer ", layer_idx, " (DETAILED): |M|=", Size(M), " |N|=", Size(NN), "\\n");
        Print("  ", Length(current), " parents\\n");

        # For detailed layers, manually trace
        USE_H1_ORBITAL := true;
        ClearH1Cache();
        local lifted;
        lifted := [];

        # Precompute hom_P
        if Size(NN) > 1 and Size(P) / Size(NN) <= 200 then
            hom_P := NaturalHomomorphismByNormalSubgroup(P, NN);
            M_bar_P := Image(hom_P, M);
        else
            hom_P := fail;
            M_bar_P := fail;
        fi;

        cachedNormPM := Normalizer(P, M);

        for i in [1..Length(current)] do
            S := current[i];

            if IsFPFSubdirect(S, shifted, offs) then
                Add(lifted, S);
            fi;

            normalsBetween := NormalSubgroupsBetween(S, M, NN);

            # Compute outer normalizer
            local cachedOuterNormGens;
            cachedOuterNormGens := [];
            N_S := Normalizer(P, S);
            outerNorm := Intersection(N_S, cachedNormPM);
            for gen in GeneratorsOfGroup(outerNorm) do
                if not gen in S then
                    if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
                        Add(cachedOuterNormGens, gen);
                    fi;
                fi;
            od;

            for L in normalsBetween do
                if Size(L) = Size(M) then
                    continue;
                fi;

                # Form quotient
                if Size(L) = Size(NN) and hom_P <> fail and Length(current) > 10 then
                    hom := hom_P;
                    Q := Image(hom_P, S);
                    M_bar := M_bar_P;
                else
                    hom := NaturalHomomorphismByNormalSubgroup(S, L);
                    Q := ImagesSource(hom);
                    M_bar := Image(hom, M);
                fi;

                if not IsElementaryAbelian(M_bar) or Size(M_bar) <= 1 then
                    continue;
                fi;

                # Filter outer norm gens for this L
                if Size(L) > 1 then
                    outerNormGens := Filtered(cachedOuterNormGens,
                        g -> ForAll(GeneratorsOfGroup(L), x -> x^g in L));
                else
                    outerNormGens := cachedOuterNormGens;
                fi;

                if Length(outerNormGens) = 0 then
                    continue;
                fi;

                # Get ALL H^1 complements (not just orbit reps)
                _TryLoadH1Orbital();
                module := ChiefFactorAsModule(Q, M_bar);
                H1 := CachedComputeH1(module);

                if H1 = fail or H1.dim = 0 then
                    continue;
                fi;

                complementInfo := BuildComplementInfo(Q, M_bar, module);
                fullCount := H1.p ^ H1.dim;

                Print("  Parent ", i, " L=", Size(L), ": |Q|=", Size(Q), " H^1 dim=", H1.dim, " p=", H1.p, " total=", fullCount, "\\n");
                Print("    outerNormGens: ", Length(outerNormGens), "\\n");

                # Enumerate ALL complements
                local allCocycles, v, cv, comp, comp_lifted, fpf;
                allCocycles := [];
                if H1.dim = 1 then
                    for j in [0..H1.p-1] do
                        Add(allCocycles, [j * One(GF(H1.p))]);
                    od;
                elif H1.dim = 2 then
                    for j in [0..H1.p^2-1] do
                        Add(allCocycles, [IntFFE(j mod H1.p) * One(GF(H1.p)), IntFFE(Int(j / H1.p)) * One(GF(H1.p))]);
                    od;
                fi;

                for j in [1..Length(allCocycles)] do
                    v := allCocycles[j];
                    cv := H1CoordsToFullCocycle(H1, v);
                    comp := CocycleToComplement(cv, complementInfo);
                    if Size(comp) * Size(M_bar) <> Size(Q) or Size(Intersection(comp, M_bar)) > 1 then
                        Print("    cocycle ", v, ": INVALID complement\\n");
                        continue;
                    fi;
                    comp_lifted := PreImages(hom, comp);
                    fpf := IsFPFSubdirect(comp_lifted, shifted, offs);
                    Print("    cocycle ", v, ": |C|=", Size(comp), " |C_lifted|=", Size(comp_lifted), " FPF=", fpf, "\\n");
                od;

                # Show orbits
                local actionMats, orbits;
                actionMats := ComputeOuterActionOnH1(module, H1, outerNormGens, Q, M_bar, S, L, hom, P);
                if actionMats <> fail then
                    orbits := ComputeH1OrbitsExplicit(H1, actionMats);
                    Print("    Orbits: ", Length(orbits), " orbits from ", fullCount, " total\\n");
                    for j in [1..Length(orbits)] do
                        Print("      orbit ", j, " rep: ", orbits[j], "\\n");
                    od;
                fi;
            od;
        od;

        # Also do the proper lifting for subsequent layers
        ClearH1Cache();
        current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
        Print(label, " Layer ", layer_idx, " (via LiftThroughLayer): ", Length(current), " results\\n");
    od;

    Print("\\n", label, " FINAL: ", Length(current), " results\\n\\n");
    return current;
end;

# Test with Size(P)
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P);
result1 := TraceLifting(P, "WITH_SIZE");

# Test without Size(P) - fresh P
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
result2 := TraceLifting(P2, "FRESH");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_fpf.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_fpf.g"

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

stdout, stderr = process.communicate(timeout=1200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    lines = stderr.strip().split('\n')
    # Only show non-syntax-warning lines
    for line in lines:
        if 'Error' in line or 'error' in line.lower():
            print(f"STDERR: {line}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['WITH_SIZE', 'FRESH', 'cocycle', 'Parent', 'orbit',
                                      'Layer', 'FINAL', 'outerNorm', 'Chief']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
