"""Per-layer diagnostic v4 for orbital bug.
Fixed: lift complements to S before conjugacy check."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_layer_diag4.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build combo: [6,5] x [6,8] x [3,2]
f1 := TransitiveGroup(6, 5);
f2 := TransitiveGroup(6, 8);
f3 := TransitiveGroup(3, 2);

shifted := [];
offs := [];
off := 0;
for factor in [f1, f2, f3] do
    Add(offs, off);
    degree := NrMovedPoints(factor);
    shift_perm := MappingPermListList([1..degree], [off+1..off+degree]);
    Add(shifted, Group(List(GeneratorsOfGroup(factor), g -> g^shift_perm)));
    off := off + degree;
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), "\\n");

# ========== RUN 1: Orbital OFF ==========
Print("\\n========== ORBITAL OFF ==========\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_off := FindFPFClassesByLifting(P, shifted, offs);
Print("Orbital OFF: ", Length(results_off), " FPF subdirects\\n");

# ========== PATCH ==========
_ORIG_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;
_DIAG_CALLS := 0;
_DIAG_MISMATCHES := 0;

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P_arg, fpfFilterFunc,
          orbitalResult, module, H1, complementInfo, allComplements,
          allFPF, dimH1, fullCount, orbitalCount,
          unmatchedCount, found, i, j, allFPF_lifted, orbital_lifted,
          liftedA, liftedB, repAction;

    orbitalResult := CallFuncList(_ORIG_GetH1OrbitRepresentatives, arg);

    if Length(arg) < 7 then return orbitalResult; fi;

    Q := arg[1];
    M_bar := arg[2];
    outerNormGens := arg[3];
    S := arg[4];
    L := arg[5];
    homSL := arg[6];
    P_arg := arg[7];
    fpfFilterFunc := fail;
    if Length(arg) >= 8 then fpfFilterFunc := arg[8]; fi;

    if Size(M_bar) = 1 or Length(outerNormGens) = 0 then
        return orbitalResult;
    fi;

    _DIAG_CALLS := _DIAG_CALLS + 1;

    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) then return orbitalResult; fi;
    if IsBound(module.isNonSplit) and module.isNonSplit then return orbitalResult; fi;
    if IsBound(module.isModuleConstructionFailed) and module.isModuleConstructionFailed then
        return orbitalResult;
    fi;

    H1 := CachedComputeH1(module);
    dimH1 := H1.H1Dimension;
    if dimH1 = 0 then return orbitalResult; fi;

    fullCount := H1.numComplements;

    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);
    if allComplements = fail then return orbitalResult; fi;

    if fpfFilterFunc <> fail then
        allFPF := Filtered(allComplements, fpfFilterFunc);
    else
        allFPF := allComplements;
    fi;

    orbitalCount := Length(orbitalResult);

    Print("  DIAG #", _DIAG_CALLS, ": |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
          " |S|=", Size(S), " dimH1=", dimH1,
          " allFPF=", Length(allFPF), " orbitalFPF=", orbitalCount);

    if Length(allFPF) <> orbitalCount then
        _DIAG_MISMATCHES := _DIAG_MISMATCHES + 1;
        Print(" *** MISMATCH #", _DIAG_MISMATCHES, " ***\\n");

        # Lift complements to S and check P-conjugacy
        allFPF_lifted := List(allFPF, c -> PreImages(homSL, c));
        orbital_lifted := List(orbitalResult, c -> PreImages(homSL, c));

        Print("    Lifted sizes - allFPF: ", List(allFPF_lifted, Size),
              " orbital: ", List(orbital_lifted, Size), "\\n");

        # Check: which allFPF lifted groups are NOT P-conjugate to any orbital lifted group?
        unmatchedCount := 0;
        for i in [1..Length(allFPF_lifted)] do
            found := false;
            for j in [1..Length(orbital_lifted)] do
                if Size(allFPF_lifted[i]) = Size(orbital_lifted[j]) then
                    repAction := RepresentativeAction(P_arg,
                        allFPF_lifted[i], orbital_lifted[j]);
                    if repAction <> fail then
                        found := true;
                        Print("    allFPF[", i, "] P-conj to orbital[", j, "] via ", repAction, "\\n");
                        break;
                    fi;
                fi;
            od;
            if not found then
                unmatchedCount := unmatchedCount + 1;
                Print("    allFPF[", i, "] NOT P-conjugate to any orbital rep!\\n");
                Print("      |G| = ", Size(allFPF_lifted[i]),
                      " IsFPF = ", IsFPFSubdirect(allFPF_lifted[i], shifted, offs), "\\n");
            fi;
        od;
        Print("    ", unmatchedCount, " truly unmatched FPF complements\\n");

        # Also check: are the 2 allFPF groups P-conjugate to EACH OTHER?
        if Length(allFPF_lifted) = 2 then
            repAction := RepresentativeAction(P_arg,
                allFPF_lifted[1], allFPF_lifted[2]);
            if repAction <> fail then
                Print("    allFPF[1] and allFPF[2] ARE P-conjugate (via ", repAction, ")\\n");
            else
                Print("    allFPF[1] and allFPF[2] are NOT P-conjugate!!!\\n");
                Print("    THIS MEANS THE ORBIT COMPUTATION IS WRONG\\n");
            fi;
        fi;

        # Print outer normalizer info
        Print("    outerNormGens: ", Length(outerNormGens), " generators\\n");
        for i in [1..Length(outerNormGens)] do
            Print("      gen ", i, " = ", outerNormGens[i],
                  " order=", Order(outerNormGens[i]),
                  " in S? ", outerNormGens[i] in S, "\\n");
        od;
    else
        Print(" OK\\n");
    fi;

    return orbitalResult;
end;

# ========== RUN 2: Orbital ON ==========
Print("\\n========== ORBITAL ON ==========\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_on := FindFPFClassesByLifting(P, shifted, offs);
Print("Orbital ON: ", Length(results_on), " FPF subdirects\\n");
Print("Diagnostic calls: ", _DIAG_CALLS, "\\n");
Print("Mismatches found: ", _DIAG_MISMATCHES, "\\n");

# ========== COMPARISON ==========
Print("\\n========== COMPARISON ==========\\n");
Print("OFF: ", Length(results_off), ", ON: ", Length(results_on), "\\n");
if Length(results_off) <> Length(results_on) then
    Print("DELTA: ", Length(results_off) - Length(results_on), "\\n");
fi;

GetH1OrbitRepresentatives := _ORIG_GetH1OrbitRepresentatives;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_layer_diag4.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_layer_diag4.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting diagnostic v4 at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(x in line for x in ['DIAG', 'MISMATCH', 'P-conj', 'NOT P-conj',
                                     '==========', 'DELTA', 'Orbital', 'P = ',
                                     'unmatched', 'ORBIT', 'outer', 'gen ',
                                     'Lifted', 'IsFPF', 'allFPF']):
            print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
