"""
Definitive test: Complete N-class analysis of Layer 8 results.

Include BOTH parents-as-candidates AND complements.
Map everything to N-classes and check which class loses its last orbital rep.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/definitive_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Definitive N-class Test ===\\n\\n");

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
Print("Parents for layer 8: ", Length(current), "\\n");

# Layer 8 parameters
M := series[numLayers];
NN := series[numLayers + 1];

# Collect ALL results with metadata
all_results := [];

for parent_idx in [1..Length(current)] do
    S := current[parent_idx];

    # Check S itself as FPF candidate
    if IsFPFSubdirect(S, shifted, offs) then
        Add(all_results, rec(
            group := S,
            parent_idx := parent_idx,
            source := "parent",
            compl_idx := 0,
            is_orbital := true,  # parents are always kept
            size := Size(S)
        ));
    fi;

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

        # Determine which complements orbital would keep
        orbital_kept_indices := [];
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
                orb_result := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, hom, P, fpfFilter);
                # Match orbital results to full complement list
                for j in [1..Length(allCompl)] do
                    for orb_c in orb_result do
                        if allCompl[j] = orb_c then
                            Add(orbital_kept_indices, j);
                            break;
                        fi;
                    od;
                od;
            fi;
        fi;

        for i in [1..Length(allCompl)] do
            isFPF := fpfFilter(allCompl[i]);
            if isFPF then
                C_lifted := PreImages(hom, allCompl[i]);

                is_orb := (H1.H1Dimension = 0) or  # unique complement, always kept
                          (i in orbital_kept_indices);

                # If no outer norm gens, all complements are kept
                if H1.H1Dimension > 0 and Length(orbital_kept_indices) = 0 then
                    is_orb := true;  # no outer norm -> no reduction
                fi;

                Add(all_results, rec(
                    group := C_lifted,
                    parent_idx := parent_idx,
                    source := "complement",
                    compl_idx := i,
                    is_orbital := is_orb,
                    size := Size(C_lifted)
                ));
            fi;
        od;
    od;
od;

Print("\\nTotal results: ", Length(all_results), "\\n");
Print("Parents: ", Length(Filtered(all_results, r -> r.source = "parent")), "\\n");
Print("Complements: ", Length(Filtered(all_results, r -> r.source = "complement")), "\\n");
Print("Orbital kept: ", Length(Filtered(all_results, r -> r.is_orbital)), "\\n");
Print("Orbital dropped: ", Length(Filtered(all_results, r -> not r.is_orbital)), "\\n\\n");

# Compute N-equivalence classes
nclasses := [];
for i in [1..Length(all_results)] do
    found := false;
    for k in [1..Length(nclasses)] do
        rep_idx := nclasses[k][1];
        if Size(all_results[i].group) = Size(all_results[rep_idx].group) then
            if RepresentativeAction(N, all_results[i].group, all_results[rep_idx].group) <> fail then
                Add(nclasses[k], i);
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Add(nclasses, [i]);
    fi;
od;

Print("N-equivalence classes: ", Length(nclasses), "\\n\\n");

for k in [1..Length(nclasses)] do
    has_orbital := false;
    class_desc := "";
    for idx in nclasses[k] do
        r := all_results[idx];
        Append(class_desc, Concatenation("[P", String(r.parent_idx), "/"));
        if r.source = "parent" then
            Append(class_desc, "self");
        else
            Append(class_desc, Concatenation("C", String(r.compl_idx)));
        fi;
        if r.is_orbital then
            Append(class_desc, "*");
            has_orbital := true;
        fi;
        Append(class_desc, "] ");
    od;
    Print("Class ", k, " (size ", Length(nclasses[k]), "): ", class_desc);
    if not has_orbital then
        Print("*** NO ORBITAL REP ***");
    fi;
    Print(" |H|=", all_results[nclasses[k][1]].size, "\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_definitive_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_definitive_test.g"

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
                                               'N-equi', 'Parents', 'Complements', 'kept',
                                               'dropped'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 4000 CHARS ===")
    print(log[-4000:])
except FileNotFoundError:
    print("Log file not found!")
