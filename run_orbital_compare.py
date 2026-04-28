"""
Compare orbital vs non-orbital complement counts at each layer.

Instruments GetH1OrbitRepresentatives to:
1. Run the orbital method (current code)
2. Run the non-orbital method (all complements)
3. Report any discrepancies

Tests on [6,6,3] partition of S15 (expected +2 with orbital disabled).
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_compare.log"

gap_commands = r'''
LogTo("''' + log_file + r'''");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Save the original function
_OrigGetH1OrbitReps := GetH1OrbitRepresentatives;

ORBITAL_COMPARE_LOG := [];

# Wrapper that compares orbital vs non-orbital at each call
GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P, fpfFilterFunc,
          orbitalResult, nonOrbitalResult,
          module, H1, complementInfo, nOrbital, nNonOrbital,
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

    # Run orbital method
    orbitalResult := CallFuncList(_OrigGetH1OrbitReps, arg);
    nOrbital := Length(orbitalResult);

    # Run non-orbital method (all complements via H^1, then FPF filter)
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
    nonOrbitalResult := EnumerateComplementsFromH1(H1, complementInfo);

    if fpfFilterFunc <> fail then
        nonOrbitalResult := Filtered(nonOrbitalResult, fpfFilterFunc);
    fi;
    nNonOrbital := Length(nonOrbitalResult);

    if nOrbital <> nNonOrbital then
        Print("\n!!! ORBITAL MISMATCH !!!\n");
        Print("  |Q|=", Size(Q), " |M_bar|=", Size(M_bar), " dimH1=", H1.H1Dimension, "\n");
        Print("  |S|=", Size(S), " |L|=", Size(L), " |P|=", Size(P), "\n");
        Print("  #outerNormGens=", Length(outerNormGens), "\n");
        Print("  Orbital: ", nOrbital, " complements\n");
        Print("  Non-orbital: ", nNonOrbital, " complements\n");
        Print("  DIFFERENCE: ", nNonOrbital - nOrbital, "\n\n");
        Add(ORBITAL_COMPARE_LOG, rec(
            sizeQ := Size(Q),
            sizeM := Size(M_bar),
            dimH1 := H1.H1Dimension,
            sizeS := Size(S),
            sizeL := Size(L),
            sizeP := Size(P),
            numOuterGens := Length(outerNormGens),
            orbital := nOrbital,
            nonOrbital := nNonOrbital,
            diff := nNonOrbital - nOrbital
        ));
        # Return the CORRECT result
        return nonOrbitalResult;
    fi;

    return orbitalResult;
end;

Print("\n=== Testing [6,6,3] partition of S15 ===\n");
Print("Start time: ", Runtime(), "\n");

result_663 := FindFPFClassesForPartition(15, [6,6,3]);
Print("\n[6,6,3] result: ", Length(result_663), "\n");
Print("Expected with orbital: 3246, expected correct: 3248\n");

Print("\n=== ORBITAL COMPARISON LOG ===\n");
if Length(ORBITAL_COMPARE_LOG) = 0 then
    Print("No mismatches detected.\n");
else
    Print(Length(ORBITAL_COMPARE_LOG), " mismatches detected:\n");
    for i in [1..Length(ORBITAL_COMPARE_LOG)] do
        Print("  Mismatch ", i, ": ", ORBITAL_COMPARE_LOG[i], "\n");
    od;
fi;

Print("\nEnd time: ", Runtime(), "\n");

LogTo();
QUIT;
'''

# Write GAP commands
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_orbital_compare.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_orbital_compare.g"

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
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    print(f"\nLog file: {len(log)} chars, {log.count(chr(10))} lines")

    # Find mismatches
    mismatch_lines = [line for line in log.split('\n') if 'MISMATCH' in line or 'ORBITAL COMPARISON' in line or 'result:' in line.lower()]
    if mismatch_lines:
        print("\n=== KEY LINES ===")
        for line in mismatch_lines:
            print(line)

    # Print last 3000 chars
    print("\n=== LAST 3000 CHARS ===")
    print(log[-3000:])
except FileNotFoundError:
    print("Log file not found!")
