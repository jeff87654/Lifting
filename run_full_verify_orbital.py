"""
Run full orbital ON for combo T(6,5) x T(6,8) x T(3,2) with verification.

Monkey-patch GetH1OrbitRepresentatives to verify that every orbit merge
produces P-conjugate complements. If any merge is wrong, report it.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/full_verify_orbital.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Monkey-patch GetH1OrbitRepresentatives to verify P-conjugacy
_OrigGetH1OrbitReps := GetH1OrbitRepresentatives;
_VERIFY_BUG_COUNT := 0;
_VERIFY_CALL_COUNT := 0;

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P_arg, fpfFilterFunc,
          module, H1, H1action, orbitReps, complementInfo,
          result, i, matIdx, mat, rep, neighbor,
          cocycle1, cocycle2, C1, C2, C1_lift, C2_lift, conj, hom;

    # Call original
    result := CallFuncList(_OrigGetH1OrbitReps, arg);

    # Extract args for verification
    if Length(arg) < 7 then
        return result;
    fi;

    Q := arg[1];
    M_bar := arg[2];
    outerNormGens := arg[3];
    S := arg[4];
    L := arg[5];
    homSL := arg[6];
    P_arg := arg[7];

    if not IsElementaryAbelian(M_bar) or Size(M_bar) = 1 then
        return result;
    fi;

    if Length(outerNormGens) = 0 then
        return result;
    fi;

    _VERIFY_CALL_COUNT := _VERIFY_CALL_COUNT + 1;

    # Recompute module and H^1 for verification
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    if not IsRecord(module) or module = fail then
        return result;
    fi;
    if IsBound(module.isNonSplit) and module.isNonSplit then
        return result;
    fi;
    if IsBound(module.isModuleConstructionFailed) and module.isModuleConstructionFailed then
        return result;
    fi;

    H1 := ComputeH1(module);

    if H1.H1Dimension = 0 then
        return result;
    fi;

    H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, homSL, P_arg);

    if H1action = fail or Length(H1action.matrices) = 0 then
        return result;
    fi;

    complementInfo := BuildComplementInfo(Q, M_bar, module);

    # Verify EVERY action matrix application
    for matIdx in [1..Length(H1action.matrices)] do
        mat := H1action.matrices[matIdx];
        for rep in H1.H1Representatives do
            neighbor := rep * mat;
            if neighbor <> rep then
                cocycle1 := H1CoordsToFullCocycle(H1, rep);
                cocycle2 := H1CoordsToFullCocycle(H1, neighbor);
                C1 := CocycleToComplement(cocycle1, complementInfo);
                C2 := CocycleToComplement(cocycle2, complementInfo);
                C1_lift := PreImages(homSL, C1);
                C2_lift := PreImages(homSL, C2);
                conj := RepresentativeAction(P_arg, C1_lift, C2_lift);
                if conj = fail then
                    _VERIFY_BUG_COUNT := _VERIFY_BUG_COUNT + 1;
                    Print("*** VERIFY BUG #", _VERIFY_BUG_COUNT,
                          " (call ", _VERIFY_CALL_COUNT,
                          "): ", rep, " -> ", neighbor,
                          " NOT P-conjugate!\\n");
                    Print("    |S|=", Size(S), " |Q|=", Size(Q),
                          " |M_bar|=", Size(M_bar),
                          " H1dim=", H1.H1Dimension, "\\n");
                    Print("    |C1_lift|=", Size(C1_lift),
                          " |C2_lift|=", Size(C2_lift), "\\n");
                    Print("    C1 FPF=", IsFPFSubdirect(C1_lift, shifted, offs),
                          " C2 FPF=", IsFPFSubdirect(C2_lift, shifted, offs), "\\n");
                fi;
            fi;
        od;
    od;

    return result;
end;

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
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Run with orbital ON (this will trigger verification)
Print("\\n=== Running with verification (orbital ON) ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();

series := RefinedChiefSeries(P);
parents := [P];
for i in [1..Length(series)-1] do
    ClearH1Cache();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
    Print("After layer ", i, ": ", Length(parents), " children\\n");
od;

Print("\\n=== Results ===\\n");
Print("Total children (orbital ON): ", Length(parents), "\\n");
Print("Verify calls: ", _VERIFY_CALL_COUNT, "\\n");
Print("Verify bugs: ", _VERIFY_BUG_COUNT, "\\n");

# Also run OFF for comparison
Print("\\n=== Running orbital OFF ===\\n");
USE_H1_ORBITAL := false;
ClearH1Cache();
FPF_SUBDIRECT_CACHE := rec();
parents_off := [P];
for i in [1..Length(series)-1] do
    ClearH1Cache();
    parents_off := LiftThroughLayer(P, series[i], series[i+1], parents_off, shifted, offs, fail);
od;
Print("Total children (orbital OFF): ", Length(parents_off), "\\n");

# Find which OFF children are missing from ON
Print("\\n=== Missing analysis ===\\n");
missing_count := 0;
for i in [1..Length(parents_off)] do
    found := false;
    for j in [1..Length(parents)] do
        if parents_off[i] = parents[j] then
            found := true;
            break;
        fi;
    od;
    if not found then
        for j in [1..Length(parents)] do
            if Size(parents_off[i]) = Size(parents[j]) then
                if RepresentativeAction(P, parents_off[i], parents[j]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
    fi;
    if not found then
        missing_count := missing_count + 1;
        Print("Not P-conjugate #", missing_count, ": |S|=", Size(parents_off[i]), "\\n");
        # Check N-conjugacy (broader test)
        found_N := false;
        for j in [1..Length(parents)] do
            if Size(parents_off[i]) = Size(parents[j]) then
                if RepresentativeAction(N, parents_off[i], parents[j]) <> fail then
                    found_N := true;
                    Print("  ... but IS N-conjugate to ON[", j, "]\\n");
                    break;
                fi;
            fi;
        od;
        if not found_N then
            Print("  ... and NOT N-conjugate to any ON result!\\n");
        fi;
    fi;
od;
Print("Total not P-conjugate to ON: ", missing_count, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_full_verify_orbital.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_full_verify_orbital.g"

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
        if any(kw in line for kw in ['VERIFY BUG', 'Results', 'Total', 'Missing',
                                      'N-conjugate', 'Verify', 'After layer',
                                      '===', 'Running', 'StructDesc',
                                      'not P-conj', 'Not P-conj']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
