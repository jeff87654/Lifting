"""
Trace descendants of the two FPF-passing complements at Layer 4.

Key question: If C1 and C2 are P-conjugate at Layer 4,
do ALL descendants of C2 have N-conjugate counterparts among
descendants of C1?

If yes -> the orbital merge is safe and the bug is elsewhere.
If no -> the orbital merge at intermediate layers is unsafe.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_descendants.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Descendant Trace ===\\n\\n");

# Build the combo
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
T63_2 := TransitiveGroup(3, 2);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

Print("|P| = ", Size(P), " |N| = ", Size(N), "\\n");

series := RefinedChiefSeries(P);
Print("Chief series lengths: ", List(series, Size), "\\n\\n");

# Step through layers 1-3 WITHOUT orbital to get the 2 parents for Layer 4
USE_H1_ORBITAL := false;
ClearH1Cache();

current := [P];
for layer_idx in [1..3] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
    Print("After layer ", layer_idx, ": ", Length(current), " subgroups\\n");
od;

Print("\\nParents for Layer 4: ", Length(current), " subgroups\\n");

# Now manually process Layer 4 to get BOTH FPF complements
M := series[4];
NN := series[5];
layerSize := Size(M) / Size(NN);
Print("\\nLayer 4: M=", Size(M), " N=", Size(NN), " factor=", layerSize, "\\n");

# Find the parent that produces multiple complements (Parent 2, |S|=1296)
S := current[2];
Print("Parent 2: |S| = ", Size(S), "\\n");

# Compute complements
normalsBetween := NormalSubgroupsBetween(S, M, NN);
L := Filtered(normalsBetween, x -> Size(x) < Size(M))[1];

hom := NaturalHomomorphismByNormalSubgroup(S, L);
Q := ImagesSource(hom);
M_bar := Image(hom, M);

Print("  |L| = ", Size(L), " |Q| = ", Size(Q), " |M_bar| = ", Size(M_bar), "\\n");

ClearH1Cache();
module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
H1 := CachedComputeH1(module);
complementInfo := BuildComplementInfo(Q, M_bar, module);
allComplements := EnumerateComplementsFromH1(H1, complementInfo);

Print("  All complement classes: ", Length(allComplements), "\\n");

# Identify FPF ones
fpfFilter := function(C_bar)
    local C_lifted;
    C_lifted := PreImages(hom, C_bar);
    return IsFPFSubdirect(C_lifted, shifted, offs);
end;

fpf_indices := [];
for i in [1..Length(allComplements)] do
    if fpfFilter(allComplements[i]) then
        Add(fpf_indices, i);
    fi;
od;
Print("  FPF indices: ", fpf_indices, "\\n");

# Lift both FPF complements to get the Layer 4 children
fpf_children := [];
for i in fpf_indices do
    C_lifted := PreImages(hom, allComplements[i]);
    Add(fpf_children, C_lifted);
    Print("  FPF child[", i, "]: |C_lifted| = ", Size(C_lifted), "\\n");
od;

# Verify P-conjugacy
conj_elem := RepresentativeAction(P, fpf_children[1], fpf_children[2]);
Print("\\n  P-conjugacy element found: ", conj_elem <> fail, "\\n");
if conj_elem <> fail then
    Print("  g = ", conj_elem, "\\n");
    # Also check: is g in N?
    Print("  g in N? ", conj_elem in N, "\\n");
    Print("  g in P? ", conj_elem in P, "\\n");
fi;

# Now lift EACH FPF child separately through layers 5-8
# Get all children from Parent 1 at Layer 4 too
parent1_child := LiftThroughLayer(P, M, NN, [current[1]], shifted, offs, fail);
Print("\\nParent 1 Layer 4 children: ", Length(parent1_child), "\\n");

# Combine Parent 1 child + FPF child 1 from Parent 2
branch1 := Concatenation(parent1_child, [fpf_children[1]]);
# Combine Parent 1 child + FPF child 2 from Parent 2
branch2 := Concatenation(parent1_child, [fpf_children[2]]);
# Combine Parent 1 child + BOTH FPF children from Parent 2
branch_both := Concatenation(parent1_child, fpf_children);

# Lift each branch through layers 5-8
Print("\\n=== Lifting branch1 (kept complement only) ===\\n");
for layer_idx in [5..8] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    USE_H1_ORBITAL := false;
    ClearH1Cache();
    branch1 := LiftThroughLayer(P, M, NN, branch1, shifted, offs, fail);
    Print("  Layer ", layer_idx, ": ", Length(branch1), " children\\n");
od;

Print("\\n=== Lifting branch2 (dropped complement only) ===\\n");
M := series[5];
NN := series[6];
branch2_copy := Concatenation(parent1_child, [fpf_children[2]]);
for layer_idx in [5..8] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    USE_H1_ORBITAL := false;
    ClearH1Cache();
    if layer_idx = 5 then
        branch2 := LiftThroughLayer(P, M, NN, branch2_copy, shifted, offs, fail);
    else
        branch2 := LiftThroughLayer(P, M, NN, branch2, shifted, offs, fail);
    fi;
    Print("  Layer ", layer_idx, ": ", Length(branch2), " children\\n");
od;

Print("\\n=== Lifting branch_both (both complements) ===\\n");
for layer_idx in [5..8] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    USE_H1_ORBITAL := false;
    ClearH1Cache();
    branch_both := LiftThroughLayer(P, M, NN, branch_both, shifted, offs, fail);
    Print("  Layer ", layer_idx, ": ", Length(branch_both), " children\\n");
od;

Print("\\n=== Final comparison ===\\n");
Print("branch1 (C1 only): ", Length(branch1), " subgroups\\n");
Print("branch2 (C2 only): ", Length(branch2), " subgroups\\n");
Print("branch_both (C1+C2): ", Length(branch_both), " subgroups\\n");

# Check: is every subgroup in branch2 P-conjugate to something in branch1?
Print("\\nChecking P-conjugacy of branch2 vs branch1...\\n");
missing_P := 0;
for i in [1..Length(branch2)] do
    found := false;
    for j in [1..Length(branch1)] do
        if Size(branch2[i]) = Size(branch1[j]) then
            if RepresentativeAction(P, branch2[i], branch1[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  branch2[", i, "] NOT P-conjugate to any in branch1. |H|=", Size(branch2[i]), "\\n");
        missing_P := missing_P + 1;
    fi;
od;
Print("Missing under P-conjugacy: ", missing_P, "\\n");

# Check: is every subgroup in branch2 N-conjugate to something in branch1?
Print("\\nChecking N-conjugacy of branch2 vs branch1...\\n");
missing_N := 0;
for i in [1..Length(branch2)] do
    found := false;
    for j in [1..Length(branch1)] do
        if Size(branch2[i]) = Size(branch1[j]) then
            if RepresentativeAction(N, branch2[i], branch1[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  branch2[", i, "] NOT N-conjugate to any in branch1. |H|=", Size(branch2[i]), "\\n");
        missing_N := missing_N + 1;
    fi;
od;
Print("Missing under N-conjugacy: ", missing_N, "\\n");

# Also check the branch_both vs branch1 comparison
Print("\\nChecking N-conjugacy of branch_both vs branch1...\\n");
missing_both := 0;
for i in [1..Length(branch_both)] do
    found := false;
    for j in [1..Length(branch1)] do
        if Size(branch_both[i]) = Size(branch1[j]) then
            if RepresentativeAction(N, branch_both[i], branch1[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("  branch_both[", i, "] NOT N-conjugate to any in branch1. |H|=", Size(branch_both[i]), "\\n");
        missing_both := missing_both + 1;
    fi;
od;
Print("Missing under N-conjugacy (both vs 1): ", missing_both, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_descendants.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_descendants.g"

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
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    # Extract key lines
    key_lines = [line for line in log.split('\n')
                 if any(kw in line for kw in ['Layer', 'branch', 'NOT', 'Missing',
                                               'conjugat', 'P-conjug', 'child',
                                               'Parent', 'FPF', 'element'])]
    print("\n=== KEY LINES ===")
    for line in key_lines:
        print(line.strip())

    print(f"\nLog: {len(log)} chars")
    print("\n=== LAST 3000 CHARS ===")
    print(log[-3000:])
except FileNotFoundError:
    print("Log file not found!")
