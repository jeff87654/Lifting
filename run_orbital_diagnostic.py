"""Diagnostic: find exactly which combo/layer in [6,6,3] loses a class with orbital ON."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"

log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_diagnostic.log"

# We'll modify GetH1OrbitRepresentatives to also compute the full complement list
# and compare. When counts differ, dump diagnostic info.
gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Patch GetH1OrbitRepresentatives to validate results
_ORIG_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;

_DIAG_COUNT := 0;
_DIAG_MISMATCHES := 0;

GetH1OrbitRepresentatives := function(arg)
    local orbitalResult, Q, M_bar, outerNormGens, S, L, homSL, P,
          fpfFilterFunc, module, H1, complementInfo, allComplements,
          fullCount, orbitalCount, i, j, found, isConj, outerNormGroup,
          n, C1, C2, fullComps, orbitalComps, unmatchedFull, unmatchedOrbital,
          actionRecord, mat, dimH1;

    # Call original
    orbitalResult := CallFuncList(_ORIG_GetH1OrbitRepresentatives, arg);

    # Only check when we have outer normalizer (7+ args) and non-trivial result
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

    # Skip trivial cases
    if Size(M_bar) = 1 or Length(outerNormGens) = 0 then
        return orbitalResult;
    fi;

    _DIAG_COUNT := _DIAG_COUNT + 1;

    # Compute ALL complements via standard method (no orbital)
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) or (IsBound(module.isNonSplit) and module.isNonSplit) then
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

    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);

    if allComplements = fail then
        return orbitalResult;
    fi;

    # Apply FPF filter to allComplements if present
    if fpfFilterFunc <> fail then
        allComplements := Filtered(allComplements, fpfFilterFunc);
    fi;

    fullCount := Length(allComplements);
    orbitalCount := Length(orbitalResult);

    if fullCount <> orbitalCount then
        _DIAG_MISMATCHES := _DIAG_MISMATCHES + 1;
        Print("\\n*** MISMATCH #", _DIAG_MISMATCHES, " at call #", _DIAG_COUNT, " ***\\n");
        Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), ", |G| = ", Size(Q)/Size(M_bar), "\\n");
        Print("  H^1 dim = ", dimH1, ", H^1 total = ", H1.numComplements, "\\n");
        Print("  Full complements (after FPF filter): ", fullCount, "\\n");
        Print("  Orbital complements: ", orbitalCount, "\\n");
        Print("  Deficit: ", fullCount - orbitalCount, "\\n");
        Print("  Outer norm gens: ", Length(outerNormGens), "\\n");

        # Build action record for diagnostics
        actionRecord := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, homSL, P);
        if actionRecord <> fail then
            Print("  Action matrices: ", Length(actionRecord.matrices), " non-identity\\n");
            for i in [1..Length(actionRecord.matrices)] do
                Print("    Matrix ", i, ": ", actionRecord.matrices[i], "\\n");
            od;
        fi;

        # Check which full complements are NOT conjugate to any orbital complement
        # under the outer normalizer
        if fullCount <= 50 and orbitalCount <= 50 then
            outerNormGroup := Group(Concatenation(outerNormGens, GeneratorsOfGroup(S)));
            unmatchedFull := [];
            for i in [1..fullCount] do
                found := false;
                for j in [1..orbitalCount] do
                    isConj := RepresentativeAction(outerNormGroup, allComplements[i], orbitalResult[j]) <> fail;
                    if isConj then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    Add(unmatchedFull, i);
                fi;
            od;
            Print("  Unmatched full complements (indices): ", unmatchedFull, "\\n");

            # Check which full complements are conjugate to each other under outerNormGroup
            if Length(unmatchedFull) > 0 then
                Print("  Checking unmatched complement details...\\n");
                for i in unmatchedFull do
                    C1 := allComplements[i];
                    Print("    Complement ", i, ": |C| = ", Size(C1),
                          ", generators = ", GeneratorsOfGroup(C1), "\\n");

                    # Get cocycle coordinates for this complement
                    # (Would need more code to extract - skip for now)
                od;
            fi;
        else
            Print("  (too many complements for conjugacy check)\\n");
        fi;

        Print("*** END MISMATCH ***\\n\\n");
    fi;

    return orbitalResult;
end;

# Now run [6,6,3] with orbital ON
USE_H1_ORBITAL := true;
Print("Running [6,6,3] with orbital ON and diagnostic...\\n");
Print("Start time: ", StringTime(Runtime()), "\\n");
result := FindFPFClassesForPartition(15, [6,6,3]);
Print("Result: ", Length(result), " classes\\n");
Print("Diagnostic calls: ", _DIAG_COUNT, "\\n");
Print("Mismatches found: ", _DIAG_MISMATCHES, "\\n");
Print("End time: ", StringTime(Runtime()), "\\n");

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_orbital_diag.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_orbital_diag.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting diagnostic at {time.strftime('%H:%M:%S')}")
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
    # Print just the mismatch sections
    lines = log.split('\n')
    in_mismatch = False
    for line in lines:
        if '*** MISMATCH' in line:
            in_mismatch = True
        if in_mismatch:
            print(line)
        if '*** END MISMATCH ***' in line:
            in_mismatch = False
    # Print summary
    for line in lines[-30:]:
        print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
