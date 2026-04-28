"""
Verify orbital H^1 correctness by checking actual P-conjugacy.

For each orbital merge (3 -> 2 orbits in [6,6,3]),
verify that the two merged complements are actually P-conjugate.

If they're NOT P-conjugate, the orbital method has a bug.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/verify_orbital.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Save original functions
_OrigGetH1OrbitReps := GetH1OrbitRepresentatives;
_OrigLiftThroughLayer := LiftThroughLayer;

VERIFY_LOG := [];
VERIFY_COUNT := 0;
MAX_VERIFY := 50;  # Stop after 50 verifications to keep runtime reasonable

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P, fpfFilterFunc,
          module, H1, complementInfo, allComplements, orbitalResult,
          nAll, nOrbital, i, j, found, isConj, conjElem,
          useOuterNorm;

    Q := arg[1];
    M_bar := arg[2];
    fpfFilterFunc := fail;

    if Length(arg) >= 7 then
        outerNormGens := arg[3];
        S := arg[4];
        L := arg[5];
        homSL := arg[6];
        P := arg[7];
        useOuterNorm := Length(outerNormGens) > 0;
        if Length(arg) >= 8 then
            fpfFilterFunc := arg[8];
        fi;
    else
        return CallFuncList(_OrigGetH1OrbitReps, arg);
    fi;

    if not useOuterNorm then
        return CallFuncList(_OrigGetH1OrbitReps, arg);
    fi;

    if VERIFY_COUNT >= MAX_VERIFY then
        return CallFuncList(_OrigGetH1OrbitReps, arg);
    fi;

    # Get orbital result (the reduced set)
    orbitalResult := CallFuncList(_OrigGetH1OrbitReps, arg);
    nOrbital := Length(orbitalResult);

    # Get ALL complements (non-orbital)
    ClearH1Cache();
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) or IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        return orbitalResult;
    fi;
    H1 := CachedComputeH1(module);
    if H1.H1Dimension = 0 then
        return orbitalResult;
    fi;
    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);

    if fpfFilterFunc <> fail then
        allComplements := Filtered(allComplements, fpfFilterFunc);
    fi;
    nAll := Length(allComplements);

    VERIFY_COUNT := VERIFY_COUNT + 1;

    if nOrbital = nAll then
        # Same count - no merging happened or merging was trivial
        return orbitalResult;
    fi;

    # MISMATCH! Orbital reduced more than expected.
    # Check: are the "extra" complements in allComplements actually P-conjugate
    # to one of the orbital results?
    Print("\\n!!! VERIFICATION CHECK ", VERIFY_COUNT, " !!!\\n");
    Print("  |Q|=", Size(Q), " |M_bar|=", Size(M_bar), " dimH1=", H1.H1Dimension, "\\n");
    Print("  |S|=", Size(S), " |L|=", Size(L), " |P|=", Size(P), "\\n");
    Print("  Orbital: ", nOrbital, " All: ", nAll, " Diff: ", nAll - nOrbital, "\\n");

    # For each complement in allComplements, check if it's P-conjugate to
    # some complement in orbitalResult
    for i in [1..nAll] do
        found := false;
        for j in [1..nOrbital] do
            # Check P-conjugacy: is there p in P such that p^-1*allC*p = orbC?
            # RepresentativeAction(P, allC, orbC) returns such p or fail
            isConj := RepresentativeAction(P, allComplements[i], orbitalResult[j]);
            if isConj <> fail then
                found := true;
                break;
            fi;
        od;

        if not found then
            Print("  COMPLEMENT ", i, " NOT P-CONJUGATE to any orbital rep!\\n");
            Print("    Size: ", Size(allComplements[i]), "\\n");
            # Check if it's even P-conjugate to another in allComplements
            for j in [1..nAll] do
                if i <> j then
                    isConj := RepresentativeAction(P, allComplements[i], allComplements[j]);
                    if isConj <> fail then
                        Print("    But IS P-conjugate to all[", j, "]\\n");
                    fi;
                fi;
            od;
        else
            Print("  Complement ", i, " IS P-conjugate to orbital[", j, "] (OK)\\n");
        fi;
    od;

    # Check if orbital reps are pairwise non-P-conjugate
    Print("  Checking orbital reps pairwise non-conjugacy...\\n");
    for i in [1..nOrbital] do
        for j in [i+1..nOrbital] do
            isConj := RepresentativeAction(P, orbitalResult[i], orbitalResult[j]);
            if isConj <> fail then
                Print("  !!! ORBITAL REPS ", i, " AND ", j, " ARE P-CONJUGATE !!!\\n");
            fi;
        od;
    od;

    Add(VERIFY_LOG, rec(
        sizeQ := Size(Q),
        sizeM := Size(M_bar),
        dimH1 := H1.H1Dimension,
        sizeS := Size(S),
        sizeL := Size(L),
        sizeP := Size(P),
        orbital := nOrbital,
        all := nAll
    ));

    # Return the non-orbital (correct) result when there's a mismatch
    if nOrbital < nAll then
        return allComplements;
    fi;
    return orbitalResult;
end;

Print("\\n=== Verifying orbital correctness on [6,6,3] of S15 ===\\n");
Print("Start time: ", Runtime(), "\\n");

result_663 := FindFPFClassesForPartition(15, [6,6,3]);
Print("\\n[6,6,3] result: ", Length(result_663), "\\n");

Print("\\n=== VERIFICATION LOG ===\\n");
if Length(VERIFY_LOG) = 0 then
    Print("No mismatches detected in first ", MAX_VERIFY, " orbital calls.\\n");
else
    Print(Length(VERIFY_LOG), " mismatches detected:\\n");
    for i in [1..Length(VERIFY_LOG)] do
        Print("  ", VERIFY_LOG[i], "\\n");
    od;
fi;

Print("\\nEnd time: ", Runtime(), "\\n");

LogTo();
QUIT;
'''

# Write GAP commands
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_verify_orbital.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_orbital.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}")
print(f"Log file: {log_file}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)  # 4 hour timeout

print(f"GAP finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

if stderr:
    print(f"STDERR: {stderr[:2000]}")

# Read the log file
try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\verify_orbital.log", "r") as f:
        log = f.read()

    # Find key lines
    key_lines = [line for line in log.split('\n')
                 if 'VERIFICATION' in line or 'MISMATCH' in line or 'NOT P-CONJUGATE' in line
                 or 'result:' in line.lower() or 'P-CONJUGATE' in line]

    if key_lines:
        print("\n=== KEY FINDINGS ===")
        for line in key_lines:
            print(line.strip())

    # Print last 5000 chars
    print("\n=== LAST 5000 CHARS ===")
    print(log[-5000:])
except FileNotFoundError:
    print("Log file not found!")
