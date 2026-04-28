"""
Debug [6,6,3] orbital: find the FIRST layer-level mismatch.

Instruments GetH1OrbitRepresentatives to detect the first call where
orbital and non-orbital produce different numbers of FPF complements.
Then logs detailed info about that call.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/debug_combo.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_OrigGetH1OrbitReps := GetH1OrbitRepresentatives;
LAYER_CALL_NUM := 0;
FIRST_MISMATCH_FOUND := false;

GetH1OrbitRepresentatives := function(arg)
    local result, Q, M_bar, outerNormGens, S, L, homSL, P, fpfFilterFunc,
          allResult, module, H1, complementInfo, i, j, isConj,
          allCompGens, orbCompGens;

    Q := arg[1];
    M_bar := arg[2];
    fpfFilterFunc := fail;

    if Length(arg) >= 7 then
        outerNormGens := arg[3];
        S := arg[4];
        L := arg[5];
        homSL := arg[6];
        P := arg[7];
        if Length(arg) >= 8 then
            fpfFilterFunc := arg[8];
        fi;
    else
        return CallFuncList(_OrigGetH1OrbitReps, arg);
    fi;

    LAYER_CALL_NUM := LAYER_CALL_NUM + 1;

    # Always run orbital
    result := CallFuncList(_OrigGetH1OrbitReps, arg);

    # If no outer norm, orbital didn't do anything, skip comparison
    if Length(outerNormGens) = 0 then
        return result;
    fi;

    # Compare with non-orbital ONLY for the first few mismatches
    if FIRST_MISMATCH_FOUND then
        return result;
    fi;

    # Get non-orbital result
    ClearH1Cache();
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) or IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        return result;
    fi;
    H1 := CachedComputeH1(module);
    if H1.H1Dimension = 0 then
        return result;
    fi;
    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allResult := EnumerateComplementsFromH1(H1, complementInfo);
    if fpfFilterFunc <> fail then
        allResult := Filtered(allResult, fpfFilterFunc);
    fi;

    if Length(result) <> Length(allResult) then
        FIRST_MISMATCH_FOUND := true;
        Print("\\n\\n========================================\\n");
        Print("FIRST LAYER MISMATCH at call #", LAYER_CALL_NUM, "\\n");
        Print("========================================\\n");
        Print("|Q|=", Size(Q), " |M_bar|=", Size(M_bar));
        Print(" dimH1=", H1.H1Dimension, "\\n");
        Print("|S|=", Size(S), " |L|=", Size(L), " |P|=", Size(P), "\\n");
        Print("#outerNormGens=", Length(outerNormGens), "\\n");
        Print("orbital=", Length(result), " all=", Length(allResult));
        Print(" diff=", Length(allResult) - Length(result), "\\n\\n");

        # Print outer norm generator info
        for i in [1..Length(outerNormGens)] do
            Print("outerNormGen[", i, "]: order=", Order(outerNormGens[i]));
            Print(" in S? ", outerNormGens[i] in S, "\\n");
        od;
        Print("\\n");

        # Print the H1 action record details
        Print("Recomputing H^1 action for debugging...\\n");
        ClearH1Cache();
        module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
        H1 := CachedComputeH1(module);
        Print("H1 dim=", H1.H1Dimension, " p=", module.p);
        Print(" numComplements=", H1.numComplements, "\\n");

        # Build action record
        Print("Building H1 action record...\\n");
        Print("Module generators: ", Length(module.generators), "\\n");
        Print("Module dimension: ", module.dimension, "\\n");
        Print("Module field: ", module.field, "\\n");

        # Compute action matrices explicitly
        for i in [1..Length(outerNormGens)] do
            Print("\\nComputing action matrix for outerNormGen[", i, "]:\\n");
            Print("  gen order = ", Order(outerNormGens[i]), "\\n");
            Print("  gen = ", outerNormGens[i], "\\n");

            # Check if this gen actually normalizes L
            if Size(L) > 1 then
                Print("  normalizes L? ",
                    ForAll(GeneratorsOfGroup(L), x -> x^(outerNormGens[i]) in L), "\\n");
            fi;

            # Compute the action matrix
            ClearH1Cache();
            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            H1 := CachedComputeH1(module);

            # Reuse the imported function from h1_action.g
            Print("  action matrix = ");
            Print(ComputeOuterActionOnH1(H1, module, outerNormGens[i], S, L, homSL, P));
            Print("\\n");
        od;

        # Now check P-conjugacy (this IS expensive but we only do it once)
        Print("\\nChecking P-conjugacy...\\n");
        Print("(This may take a while for large |P|)\\n");
        for i in [1..Length(allResult)] do
            isConj := false;
            for j in [1..Length(result)] do
                if RepresentativeAction(P, allResult[i], result[j]) <> fail then
                    isConj := true;
                    Print("all[", i, "] ~ orb[", j, "] (P-conjugate)\\n");
                    break;
                fi;
            od;
            if not isConj then
                Print("*** all[", i, "] NOT P-conjugate to any orbital rep! ***\\n");
                Print("  |all[", i, "]| = ", Size(allResult[i]), "\\n");
                # Print generators
                allCompGens := GeneratorsOfGroup(allResult[i]);
                Print("  gens: ", allCompGens, "\\n");
            fi;
        od;

        Print("\\nOrbital reps pairwise check:\\n");
        for i in [1..Length(result)] do
            for j in [i+1..Length(result)] do
                if RepresentativeAction(P, result[i], result[j]) <> fail then
                    Print("*** orb[", i, "] ~ orb[", j, "] ARE P-conjugate! ***\\n");
                fi;
            od;
        od;

        Print("\\n========== END MISMATCH DIAGNOSTIC ==========\\n\\n");

        # Return non-orbital result (correct)
        return allResult;
    fi;

    return result;
end;

Print("\\n=== Debug [6,6,3] orbital mismatch ===\\n");
Print("Start: ", Runtime(), "\\n");

result := FindFPFClassesForPartition(15, [6,6,3]);
Print("\\nResult: ", Length(result), "\\n");
Print("Layer calls: ", LAYER_CALL_NUM, "\\n");
Print("End: ", Runtime(), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_combo.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_combo.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")
print(f"Log: {log_file}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    key_lines = [line for line in log.split('\n')
                 if 'MISMATCH' in line or 'NOT P-conjugate' in line or 'Result:' in line
                 or 'action matrix' in line or 'P-conjugate' in line.lower()
                 or 'ARE P-conjugate' in line]
    if key_lines:
        print("\n=== KEY FINDINGS ===")
        for line in key_lines:
            print(line.strip())

    # Print everything between MISMATCH markers
    if 'FIRST LAYER MISMATCH' in log:
        start = log.index('FIRST LAYER MISMATCH')
        end = log.index('END MISMATCH DIAGNOSTIC') if 'END MISMATCH DIAGNOSTIC' in log else start + 3000
        print("\n=== MISMATCH DETAILS ===")
        print(log[start:end+50])
    else:
        print("\nNo mismatch found! (Bug might not trigger in this run)")

    print(f"\nLog: {len(log)} chars, {log.count(chr(10))} lines")
    print("\n=== LAST 1000 CHARS ===")
    print(log[-1000:])
except FileNotFoundError:
    print("Log file not found!")
