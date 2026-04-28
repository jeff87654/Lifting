"""Per-layer diagnostic v2 for orbital bug.
Runs [6,5] x [6,8] x [3,2] with orbital ON/OFF, compares results,
and patches GetH1OrbitRepresentatives WITHOUT the <= 1 guard."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_layer_diag2.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build combo: [6,5] x [6,8] x [3,2]
f1 := TransitiveGroup(6, 5);
f2 := TransitiveGroup(6, 8);
f3 := TransitiveGroup(3, 2);

Print("Factor structures:\\n");
Print("  f1 = TransitiveGroup(6,5) = ", StructureDescription(f1), ", |f1| = ", Size(f1), "\\n");
Print("  f2 = TransitiveGroup(6,8) = ", StructureDescription(f2), ", |f2| = ", Size(f2), "\\n");
Print("  f3 = TransitiveGroup(3,2) = ", StructureDescription(f3), ", |f3| = ", Size(f3), "\\n");

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
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), ", degree = ", off, "\\n");
Print("Chief series length: ", Length(RefinedChiefSeries(P)), "\\n\\n");

# Print chief series
series := RefinedChiefSeries(P);
for i in [1..Length(series)-1] do
    layerSize := Size(series[i]) / Size(series[i+1]);
    Print("  Layer ", i, ": |M/N| = ", layerSize, ", |M| = ", Size(series[i]), "\\n");
od;
Print("\\n");

# ========== PATCH GetH1OrbitRepresentatives ==========
_ORIG_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;
_DIAG_CALLS := 0;
_DIAG_MISMATCHES := 0;

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P_arg, fpfFilterFunc,
          orbitalResult, module, H1, complementInfo, allComplements,
          allFPF, orbitalFPF, dimH1, fullCount, orbitalCount;

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

    # NO guard on Length(orbitalResult) <= 1 -- check ALL cases!

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

    # Enumerate ALL complements
    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);
    if allComplements = fail then return orbitalResult; fi;

    # Apply FPF filter to ALL
    if fpfFilterFunc <> fail then
        allFPF := Filtered(allComplements, fpfFilterFunc);
    else
        allFPF := allComplements;
    fi;

    orbitalCount := Length(orbitalResult);

    # ALWAYS report
    Print("  DIAG call #", _DIAG_CALLS, ": |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
          " dimH1=", dimH1, " total=", fullCount,
          " allFPF=", Length(allFPF), " orbitalFPF=", orbitalCount);

    if Length(allFPF) <> orbitalCount then
        _DIAG_MISMATCHES := _DIAG_MISMATCHES + 1;
        Print(" *** MISMATCH #", _DIAG_MISMATCHES, " ***");

        # Check: are the allFPF members truly distinct complement classes?
        # i.e., which allFPF are NOT P-conjugate to any orbitalFPF?
        if Length(allFPF) <= 20 and orbitalCount <= 20 then
            Print("\\n");
            unmatchedCount := 0;
            for i in [1..Length(allFPF)] do
                found := false;
                for j in [1..orbitalCount] do
                    if RepresentativeAction(P_arg, allFPF[i], orbitalResult[j]) <> fail then
                        found := true;
                        break;
                    fi;
                od;
                if not found then
                    unmatchedCount := unmatchedCount + 1;
                    Print("    allFPF[", i, "] (|G|=", Size(allFPF[i]), ") NOT P-conjugate to any orbital rep!\\n");
                fi;
            od;
            Print("    ", unmatchedCount, " truly unmatched FPF complements\\n");
        fi;
    else
        Print(" OK\\n");
    fi;

    return orbitalResult;
end;

# ========== RUN 1: Orbital OFF ==========
Print("\\n========== ORBITAL OFF ==========\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
results_off := FindFPFClassesByLifting(P, shifted, offs);
t_off := Runtime() - t0;
Print("Orbital OFF: ", Length(results_off), " FPF subdirects in ", t_off, "ms\\n");

# ========== RUN 2: Orbital ON (with diagnostic) ==========
Print("\\n========== ORBITAL ON (with diagnostic) ==========\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
results_on := FindFPFClassesByLifting(P, shifted, offs);
t_on := Runtime() - t0;
Print("Orbital ON: ", Length(results_on), " FPF subdirects in ", t_on, "ms\\n");
Print("Diagnostic calls: ", _DIAG_CALLS, "\\n");
Print("Mismatches found: ", _DIAG_MISMATCHES, "\\n\\n");

# ========== FINAL COMPARISON ==========
Print("========== FINAL COMPARISON ==========\\n");
Print("OFF: ", Length(results_off), " groups\\n");
Print("ON: ", Length(results_on), " groups\\n");

if Length(results_off) <> Length(results_on) then
    Print("DELTA: ", Length(results_off) - Length(results_on), "\\n\\n");

    # Find unmatched groups
    unmatched_off := [];
    for i in [1..Length(results_off)] do
        found := false;
        for j in [1..Length(results_on)] do
            if Size(results_off[i]) = Size(results_on[j]) then
                if RepresentativeAction(P, results_off[i], results_on[j]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(unmatched_off, i);
        fi;
    od;

    Print("Unmatched OFF groups (not P-conjugate to any ON group): ", Length(unmatched_off), "\\n");
    for idx in unmatched_off do
        G := results_off[idx];
        Print("  Group ", idx, ": |G|=", Size(G), " ", StructureDescription(G),
              " AbelInv=", SortedList(AbelianInvariants(G)), "\\n");
    od;

    # Check reverse
    unmatched_on := [];
    for j in [1..Length(results_on)] do
        found := false;
        for i in [1..Length(results_off)] do
            if Size(results_on[j]) = Size(results_off[i]) then
                if RepresentativeAction(P, results_on[j], results_off[i]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(unmatched_on, j);
        fi;
    od;
    if Length(unmatched_on) > 0 then
        Print("WARNING: ", Length(unmatched_on), " ON groups not matched!\\n");
    else
        Print("All ON groups matched to some OFF group.\\n");
    fi;
fi;

# Restore
GetH1OrbitRepresentatives := _ORIG_GetH1OrbitRepresentatives;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_layer_diag2.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_layer_diag2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting diagnostic v2 at {time.strftime('%H:%M:%S')}")
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
    else:
        print("(stderr present but no errors)")

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(x in line for x in ['==========', 'DELTA', 'Unmatched', 'MISMATCH',
                                     'DIAG call', 'Orbital', 'Factor', 'Chief',
                                     'Layer ', 'P = ', 'Degree', 'matched', 'WARNING',
                                     'truly unmatched', 'NOT P-conjugate']):
            print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
