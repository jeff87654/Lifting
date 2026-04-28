"""Deep diagnostic: For each GetH1OrbitRepresentatives call with non-trivial orbits,
compare ALL complements (with FPF status) vs orbital orbit reps.
Only runs if A/B test shows orbital is still broken."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_deep_diag.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Patch GetH1OrbitRepresentatives to validate orbit correctness
_ORIG_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;

_DIAG_CALLS := 0;
_DIAG_MISMATCHES := 0;

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P, fpfFilterFunc,
          orbitalResult, module, H1, complementInfo, allComplements,
          allFPF, orbitalFPF, orbitalFPFset, unmatchedFPF,
          outerNormGroup, i, j, found, isConj, dimH1, orbitReps,
          H1action, numOrbits, fullCount, orbitalCount,
          rep, cocycleVec, C, vec, h1coords;

    # Call original to get orbital result
    orbitalResult := CallFuncList(_ORIG_GetH1OrbitRepresentatives, arg);

    # Only check calls with outer normalizer
    if Length(arg) < 7 then
        return orbitalResult;
    fi;

    Q := arg[1];
    M_bar := arg[2];
    outerNormGens := arg[3];
    S := arg[4];
    L := arg[5];
    homSL := arg[6];
    P := arg[7];
    fpfFilterFunc := fail;
    if Length(arg) >= 8 then
        fpfFilterFunc := arg[8];
    fi;

    if Size(M_bar) = 1 or Length(outerNormGens) = 0 then
        return orbitalResult;
    fi;

    _DIAG_CALLS := _DIAG_CALLS + 1;

    # Skip if orbital returned <= 1 (no reduction happening)
    if Length(orbitalResult) <= 1 then
        return orbitalResult;
    fi;

    # Compute module and H^1
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) then
        return orbitalResult;
    fi;
    if IsBound(module.isNonSplit) and module.isNonSplit then
        return orbitalResult;
    fi;
    if IsBound(module.isModuleConstructionFailed) and module.isModuleConstructionFailed then
        return orbitalResult;
    fi;

    H1 := CachedComputeH1(module);
    dimH1 := H1.H1Dimension;
    if dimH1 = 0 then
        return orbitalResult;
    fi;

    fullCount := H1.numComplements;

    # Only check cases where orbital reduces (non-trivial action)
    if fullCount <= Length(orbitalResult) then
        return orbitalResult;
    fi;

    # Enumerate ALL complements
    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);
    if allComplements = fail then
        return orbitalResult;
    fi;

    # Apply FPF filter to all
    if fpfFilterFunc <> fail then
        allFPF := Filtered(allComplements, fpfFilterFunc);
    else
        allFPF := allComplements;
    fi;

    # Apply FPF filter to orbital result (already filtered, just count)
    orbitalFPF := orbitalResult;
    # orbital result already has FPF filter applied

    orbitalCount := Length(orbitalFPF);

    # Only report if counts differ
    if Length(allFPF) = orbitalCount then
        return orbitalResult;
    fi;

    _DIAG_MISMATCHES := _DIAG_MISMATCHES + 1;
    Print("\\n*** ORBIT MISMATCH #", _DIAG_MISMATCHES, " at call #", _DIAG_CALLS, " ***\\n");
    Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), ", |G| = ", Size(Q)/Size(M_bar), "\\n");
    Print("  H^1 dim = ", dimH1, ", p = ", module.p, ", total H^1 = ", fullCount, "\\n");
    Print("  All complements: ", Length(allComplements), "\\n");
    Print("  All FPF: ", Length(allFPF), "\\n");
    Print("  Orbital FPF: ", orbitalCount, "\\n");
    Print("  Deficit: ", Length(allFPF) - orbitalCount, "\\n");
    Print("  Outer norm gens: ", Length(outerNormGens), "\\n");

    # Check actual conjugacy: which allFPF are NOT conjugate to any orbitalFPF under outerNormGroup?
    if Length(allFPF) <= 30 and orbitalCount <= 30 then
        outerNormGroup := Group(Concatenation(outerNormGens, GeneratorsOfGroup(S)));

        unmatchedFPF := [];
        for i in [1..Length(allFPF)] do
            found := false;
            for j in [1..orbitalCount] do
                isConj := RepresentativeAction(outerNormGroup, allFPF[i], orbitalFPF[j]) <> fail;
                if isConj then
                    found := true;
                    break;
                fi;
            od;
            if not found then
                Add(unmatchedFPF, i);
            fi;
        od;
        Print("  Unmatched FPF (not conjugate to any orbital rep): ", unmatchedFPF, "\\n");

        if Length(unmatchedFPF) > 0 then
            # For each unmatched, check if it's conjugate to any OTHER allFPF
            Print("  Checking true conjugacy classes among all FPF...\\n");
            for i in unmatchedFPF do
                Print("    Unmatched #", i, ": |C| = ", Size(allFPF[i]), "\\n");
                # Check if it's conjugate to any orbital rep under FULL P
                for j in [1..orbitalCount] do
                    isConj := RepresentativeAction(P, allFPF[i], orbitalFPF[j]) <> fail;
                    if isConj then
                        Print("      -> P-conjugate to orbital rep ", j, "!\\n");
                        Print("      This means the orbital rep was ALSO FPF but filtered differently\\n");
                        break;
                    fi;
                od;
            od;

            # Compute H^1 action record and orbits for diagnostics
            H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, homSL, P);
            if H1action <> fail then
                Print("  Action matrices (", Length(H1action.matrices), " non-identity):\\n");
                for i in [1..Length(H1action.matrices)] do
                    Print("    M", i, " = ", H1action.matrices[i], "\\n");
                od;

                orbitReps := ComputeH1Orbits(H1action);
                Print("  Orbit reps (", Length(orbitReps), " orbits): ", orbitReps, "\\n");
            fi;
        fi;
    else
        Print("  (too many complements for conjugacy check)\\n");
    fi;

    Print("*** END ORBIT MISMATCH ***\\n\\n");

    return orbitalResult;
end;

# Run [6,6,3]
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("Running [6,6,3] with orbital ON and deep diagnostic...\\n");
Print("Start time: ", StringTime(Runtime()), "\\n");
result := FindFPFClassesForPartition(15, [6,6,3]);
Print("Result: ", Length(result), " classes\\n");
Print("Diagnostic calls: ", _DIAG_CALLS, "\\n");
Print("Mismatches found: ", _DIAG_MISMATCHES, "\\n");
Print("End time: ", StringTime(Runtime()), "\\n");

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_deep_diag.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_deep_diag.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting deep diagnostic at {time.strftime('%H:%M:%S')}")
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
    # Print mismatch sections
    lines = log.split('\n')
    in_mismatch = False
    for line in lines:
        if '*** ORBIT MISMATCH' in line:
            in_mismatch = True
        if in_mismatch:
            print(line)
        if '*** END ORBIT MISMATCH ***' in line:
            in_mismatch = False
    # Print summary
    print("---")
    for line in lines[-30:]:
        print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
