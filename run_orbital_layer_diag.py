"""Per-layer diagnostic for orbital bug.
Runs the specific affected combo [6,5] x [6,8] x [3,2] with orbital ON and OFF,
comparing the results at each layer to find where the divergence occurs.
Also identifies the specific missing group."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_layer_diag.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build the specific combo: [6,5] x [6,8] x [3,2]
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
Print("Degree: ", off, "\\n");

# ========== RUN 1: Orbital OFF ==========
Print("\\n========== ORBITAL OFF ==========\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
results_off := FindFPFClassesByLifting(P, shifted, offs);
t_off := Runtime() - t0;
Print("Orbital OFF: ", Length(results_off), " FPF subdirects in ", t_off, "ms\\n");

# ========== RUN 2: Orbital ON ==========
Print("\\n========== ORBITAL ON ==========\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
results_on := FindFPFClassesByLifting(P, shifted, offs);
t_on := Runtime() - t0;
Print("Orbital ON: ", Length(results_on), " FPF subdirects in ", t_on, "ms\\n");

# ========== COMPARISON ==========
Print("\\n========== COMPARISON ==========\\n");
Print("OFF: ", Length(results_off), ", ON: ", Length(results_on), "\\n");

if Length(results_off) <> Length(results_on) then
    Print("DELTA: ", Length(results_off) - Length(results_on), " missing with orbital ON\\n\\n");

    # For each group in OFF, check if P-conjugate to any group in ON
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

    Print("Unmatched groups from OFF (not P-conjugate to any ON group):\\n");
    for idx in unmatched_off do
        G := results_off[idx];
        Print("  Group ", idx, ":\\n");
        Print("    |G| = ", Size(G), "\\n");
        Print("    StructureDescription = ", StructureDescription(G), "\\n");
        Print("    AbelianInvariants = ", SortedList(AbelianInvariants(G)), "\\n");
        # Check projections onto each orbit
        for k in [1..Length(shifted)] do
            proj := RestrictedPerm(G, [offs[k]+1..offs[k]+NrMovedPoints(shifted[k])]);
            proj_grp := Group(List(GeneratorsOfGroup(G),
                g -> RestrictedPerm(g, [offs[k]+1..offs[k]+NrMovedPoints(shifted[k])])));
            Print("    Orbit ", k, " (deg ", NrMovedPoints(shifted[k]), "): proj order = ", Size(proj_grp), "\\n");
        od;
        Print("    Generators: ", GeneratorsOfGroup(G), "\\n");
        Print("\\n");
    od;

    # Also check: are any ON groups not P-conjugate to any OFF group?
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
        Print("WARNING: ", Length(unmatched_on), " ON groups not matched to any OFF group!\\n");
    else
        Print("All ON groups are P-conjugate to some OFF group. Good.\\n");
    fi;
else
    Print("SAME COUNT - no divergence for this combo\\n");
fi;

# ========== LAYER-BY-LAYER TRACE ==========
# Now trace with instrumented LiftThroughLayer
Print("\\n========== LAYER-BY-LAYER TRACE ==========\\n");

# Save original LiftThroughLayer
_ORIG_LiftThroughLayer := LiftThroughLayer;

# Instrumented version that logs layer details
_LAYER_LOG_OFF := [];
_LAYER_LOG_ON := [];
_CURRENT_LOG := fail;

LiftThroughLayer := function(P, M, N, subgroups_containing_M, shifted_factors, offsets, partNormalizer)
    local result, layerSize;
    layerSize := Size(M) / Size(N);
    result := _ORIG_LiftThroughLayer(P, M, N, subgroups_containing_M, shifted_factors, offsets, partNormalizer);
    if _CURRENT_LOG <> fail then
        Add(_CURRENT_LOG, rec(
            layerSize := layerSize,
            numParents := Length(subgroups_containing_M),
            numResults := Length(result),
            parentSizes := List(subgroups_containing_M, Size),
            resultSizes := List(result, Size)
        ));
    fi;
    return result;
end;

# Run OFF trace
Print("--- OFF trace ---\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_CURRENT_LOG := _LAYER_LOG_OFF;
results_off2 := FindFPFClassesByLifting(P, shifted, offs);
Print("OFF trace: ", Length(results_off2), " results, ", Length(_LAYER_LOG_OFF), " layers\\n");

# Run ON trace
Print("--- ON trace ---\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_CURRENT_LOG := _LAYER_LOG_ON;
results_on2 := FindFPFClassesByLifting(P, shifted, offs);
Print("ON trace: ", Length(results_on2), " results, ", Length(_LAYER_LOG_ON), " layers\\n");

# Compare traces
Print("\\n--- Layer comparison ---\\n");
for i in [1..Maximum(Length(_LAYER_LOG_OFF), Length(_LAYER_LOG_ON))] do
    if i <= Length(_LAYER_LOG_OFF) and i <= Length(_LAYER_LOG_ON) then
        lo := _LAYER_LOG_OFF[i];
        ln := _LAYER_LOG_ON[i];
        delta_parents := lo.numParents - ln.numParents;
        delta_results := lo.numResults - ln.numResults;
        marker := "";
        if delta_parents <> 0 or delta_results <> 0 then
            marker := " <-- DIVERGENCE";
        fi;
        Print("Layer ", i, " (|M/N|=", lo.layerSize, "): ",
              "OFF parents=", lo.numParents, " results=", lo.numResults,
              " | ON parents=", ln.numParents, " results=", ln.numResults,
              " | delta_parents=", delta_parents, " delta_results=", delta_results,
              marker, "\\n");
    fi;
od;

# Restore original
LiftThroughLayer := _ORIG_LiftThroughLayer;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_layer_diag.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_layer_diag.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting orbital layer diagnostic at {time.strftime('%H:%M:%S')}")
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
    # Print key sections
    in_section = False
    for line in lines:
        if any(x in line for x in ['==========', 'DELTA', 'Unmatched', 'Group ', 'Layer ',
                                     'DIVERGENCE', 'ORBITAL', 'OFF:', 'ON:', 'SAME COUNT',
                                     'All ON', 'WARNING', 'trace:', '--- ']):
            print(line)
        elif 'P = ' in line or 'Degree:' in line:
            print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
