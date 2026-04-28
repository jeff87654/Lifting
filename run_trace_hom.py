"""
Trace the exact hom and C_bar for the two cases.
Focus on a specific parent where FPF differs.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_hom.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

Print("\\n=== Trace hom effect on FPF ===\\n\\n");

# Build P both ways
P_stab := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P_stab);  # triggers StabChain

P_fresh := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
# No Size call, no StabChain

# Get chief series for both
series_stab := RefinedChiefSeries(P_stab);
series_fresh := RefinedChiefSeries(P_fresh);

Print("Stab series sizes: ", List(series_stab, Size), "\\n");
Print("Fresh series sizes: ", List(series_fresh, Size), "\\n\\n");

# Check if series are the same
same_series := true;
for i in [1..Length(series_stab)] do
    if Size(series_stab[i]) <> Size(series_fresh[i]) then
        Print("Series differ at position ", i, "!\\n");
        same_series := false;
    fi;
od;
if same_series then
    Print("Series sizes match.\\n");
fi;

# Lift through layers 1-7 for both (orbital ON)
USE_H1_ORBITAL := true;
ClearH1Cache();

current_stab := [P_stab];
for i in [1..7] do
    M := series_stab[i];
    NN := series_stab[i+1];
    ClearH1Cache();
    current_stab := LiftThroughLayer(P_stab, M, NN, current_stab, shifted, offs, fail);
od;
Print("\\nAfter layer 7, stab: ", Length(current_stab), " parents\\n");

ClearH1Cache();
current_fresh := [P_fresh];
for i in [1..7] do
    M := series_fresh[i];
    NN := series_fresh[i+1];
    ClearH1Cache();
    current_fresh := LiftThroughLayer(P_fresh, M, NN, current_fresh, shifted, offs, fail);
od;
Print("After layer 7, fresh: ", Length(current_fresh), " parents\\n\\n");

# Now trace layer 8 manually for both
Print("=== Layer 8 detail ===\\n\\n");
M_stab := series_stab[8];
N_stab := series_stab[9];
M_fresh := series_fresh[8];
N_fresh := series_fresh[9];

Print("Stab layer 8: |M|=", Size(M_stab), " |N|=", Size(N_stab), "\\n");
Print("Fresh layer 8: |M|=", Size(M_fresh), " |N|=", Size(N_fresh), "\\n\\n");

# For each parent in stab, find normalsBetween and check FPF of complements
for idx in [1..Length(current_stab)] do
    S := current_stab[idx];
    normalsBetween := NormalSubgroupsBetween(S, M_stab, N_stab);
    for L in normalsBetween do
        if Size(L) = Size(M_stab) then
            continue;
        fi;

        # Fresh quotient (per-parent)
        hom := NaturalHomomorphismByNormalSubgroup(S, L);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M_stab);

        if not IsElementaryAbelian(M_bar) or Size(M_bar) <= 1 then
            continue;
        fi;

        _TryLoadH1Orbital();
        module := ChiefFactorAsModule(Q, M_bar);
        H1 := CachedComputeH1(module);
        if H1 = fail or H1.dim = 0 then
            continue;
        fi;

        complementInfo := BuildComplementInfo(Q, M_bar, module);

        Print("STAB Parent ", idx, ": |S|=", Size(S), " |Q|=", Size(Q), " |M_bar|=", Size(M_bar), " H^1 dim=", H1.dim, " p=", H1.p, "\\n");

        # Enumerate all H^1 points
        for j in [0..H1.p^H1.dim - 1] do
            v := [];
            temp := j;
            for k in [1..H1.dim] do
                Add(v, (temp mod H1.p) * One(GF(H1.p)));
                temp := Int(temp / H1.p);
            od;
            cv := H1CoordsToFullCocycle(H1, v);
            comp := CocycleToComplement(cv, complementInfo);
            if Size(comp) * Size(M_bar) <> Size(Q) then
                continue;
            fi;
            comp_lifted := PreImages(hom, comp);
            fpf := IsFPFSubdirect(comp_lifted, shifted, offs);
            Print("  v=", List(v, IntFFE), " |C_lifted|=", Size(comp_lifted), " FPF=", fpf, "\\n");
        od;
    od;
od;

Print("\\n");

# Same for fresh
for idx in [1..Length(current_fresh)] do
    S := current_fresh[idx];
    normalsBetween := NormalSubgroupsBetween(S, M_fresh, N_fresh);
    for L in normalsBetween do
        if Size(L) = Size(M_fresh) then
            continue;
        fi;

        hom := NaturalHomomorphismByNormalSubgroup(S, L);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M_fresh);

        if not IsElementaryAbelian(M_bar) or Size(M_bar) <= 1 then
            continue;
        fi;

        _TryLoadH1Orbital();
        ClearH1Cache();
        module := ChiefFactorAsModule(Q, M_bar);
        H1 := CachedComputeH1(module);
        if H1 = fail or H1.dim = 0 then
            continue;
        fi;

        complementInfo := BuildComplementInfo(Q, M_bar, module);

        Print("FRESH Parent ", idx, ": |S|=", Size(S), " |Q|=", Size(Q), " |M_bar|=", Size(M_bar), " H^1 dim=", H1.dim, " p=", H1.p, "\\n");

        for j in [0..H1.p^H1.dim - 1] do
            v := [];
            temp := j;
            for k in [1..H1.dim] do
                Add(v, (temp mod H1.p) * One(GF(H1.p)));
                temp := Int(temp / H1.p);
            od;
            cv := H1CoordsToFullCocycle(H1, v);
            comp := CocycleToComplement(cv, complementInfo);
            if Size(comp) * Size(M_bar) <> Size(Q) then
                continue;
            fi;
            comp_lifted := PreImages(hom, comp);
            fpf := IsFPFSubdirect(comp_lifted, shifted, offs);
            Print("  v=", List(v, IntFFE), " |C_lifted|=", Size(comp_lifted), " FPF=", fpf, "\\n");
        od;
    od;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_hom.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_hom.g"

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

stdout, stderr = process.communicate(timeout=1200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    for line in stderr.strip().split('\n'):
        if 'Error' in line:
            print(f"STDERR: {line}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['STAB', 'FRESH', 'v=', 'Parent', 'Layer',
                                      'Series', 'layer', 'series', 'FINAL',
                                      'Stab', 'Fresh']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
