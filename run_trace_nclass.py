"""
Check which N-class each Layer 8 result belongs to.

The hypothesis: orbital drops a complement C from parent X. C is N-conjugate
to the kept complement C' from parent X. But C is also the SOLE representative
of some N-class K. Meanwhile C' is N-conjugate to a result from parent Y.
So dropping C loses class K entirely.

This happens when N-conjugacy merges across parents in a way that
doesn't respect the within-parent P-conjugacy.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_nclass.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== N-class Analysis at Layer 8 ===\\n\\n");

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

# Lift through layers 1-7 WITHOUT orbital
USE_H1_ORBITAL := false;
ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers-1] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
od;

# Layer 8 manually
M := series[numLayers];
NN := series[numLayers + 1];

# Collect ALL complements with parent info
all_results := [];  # list of rec(group, parent_idx, is_orbital, h1_coord)

for parent_idx in [1..Length(current)] do
    S := current[parent_idx];
    normalsBetween := NormalSubgroupsBetween(S, M, NN);

    for L in normalsBetween do
        if Size(L) = Size(M) then continue; fi;

        hom := NaturalHomomorphismByNormalSubgroup(S, L);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        if not IsElementaryAbelian(M_bar) or Size(M_bar) = 1 then continue; fi;

        ClearH1Cache();
        module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
        if not IsRecord(module) or IsBound(module.isNonSplit) then continue; fi;
        H1 := CachedComputeH1(module);

        complInfo := BuildComplementInfo(Q, M_bar, module);
        allCompl := EnumerateComplementsFromH1(H1, complInfo);

        fpfFilter := function(C_bar)
            local C_lifted;
            C_lifted := PreImages(hom, C_bar);
            return IsFPFSubdirect(C_lifted, shifted, offs);
        end;

        # Find out which complements the orbital would keep
        orbital_kept := [];
        if H1.H1Dimension > 0 then
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
            if Size(L) > 1 then
                outerNormGens := Filtered(outerNormGens,
                    gen -> ForAll(GeneratorsOfGroup(L), x -> x^gen in L));
            fi;

            if Length(outerNormGens) > 0 then
                ClearH1Cache();
                orbital_kept := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, hom, P, fpfFilter);
            fi;
        fi;

        for i in [1..Length(allCompl)] do
            isFPF := fpfFilter(allCompl[i]);
            if isFPF then
                C_lifted := PreImages(hom, allCompl[i]);

                # Is this complement kept by orbital?
                is_orb_kept := false;
                for j in [1..Length(orbital_kept)] do
                    if allCompl[i] = orbital_kept[j] then
                        is_orb_kept := true;
                        break;
                    fi;
                od;

                Add(all_results, rec(
                    group := C_lifted,
                    parent_idx := parent_idx,
                    compl_idx := i,
                    is_orbital := is_orb_kept,
                    size := Size(C_lifted)
                ));
            fi;
        od;
    od;
od;

Print("Total results: ", Length(all_results), "\\n");
Print("Orbital kept: ", Length(Filtered(all_results, r -> r.is_orbital)), "\\n");
Print("Orbital dropped: ", Length(Filtered(all_results, r -> not r.is_orbital)), "\\n\\n");

# Compute N-equivalence classes
nclasses := [];  # each entry: list of indices in all_results
for i in [1..Length(all_results)] do
    found := false;
    for k in [1..Length(nclasses)] do
        rep_idx := nclasses[k][1];
        if RepresentativeAction(N, all_results[i].group, all_results[rep_idx].group) <> fail then
            Add(nclasses[k], i);
            found := true;
            break;
        fi;
    od;
    if not found then
        Add(nclasses, [i]);
    fi;
od;

Print("N-equivalence classes: ", Length(nclasses), "\\n\\n");

for k in [1..Length(nclasses)] do
    Print("Class ", k, " (size ", Length(nclasses[k]), "): ");
    has_orbital := false;
    for idx in nclasses[k] do
        r := all_results[idx];
        Print("[P", r.parent_idx, "/C", r.compl_idx);
        if r.is_orbital then
            Print("*");
            has_orbital := true;
        fi;
        Print("] ");
    od;
    if not has_orbital then
        Print("*** NO ORBITAL REP ***");
    fi;
    Print(" |H|=", all_results[nclasses[k][1]].size, "\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_nclass.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_nclass.g"

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

    key_lines = [line for line in log.split('\n')
                 if any(kw in line for kw in ['Class', 'Total', 'Orbital', 'NO ORBITAL',
                                               'N-equi'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 3000 CHARS ===")
    print(log[-3000:])
except FileNotFoundError:
    print("Log file not found!")
