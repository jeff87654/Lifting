"""Quick test: GF(2) dedup normalizer computation on S16 partitions."""

import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_gf2fix.log"
BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Test 1: Reproduce the exact groups from the failing cases
# For partition [4,4,2,2,2,2] of S16, combo [[4,2],[4,2],[2,1]x4]
# Build P = V_4^2 x C_2^4 = C_2^8 acting on 16 points

# Use the real code path to build P
Print("=== Test: Building P for [4,4,2,2,2,2] combo [[4,2],[4,2],[2,1]x4] ===\\n");
partition := [4,4,2,2,2,2];
comboIndices := [[4,2],[4,2],[2,1],[2,1],[2,1],[2,1]];

# Build shifted factors exactly as FindFPFClassesForPartition does
_shifted := [];
_offs := [];
off := 0;
for ci in comboIndices do
    deg := ci[1];
    idx := ci[2];
    G := TransitiveGroup(deg, idx);
    # Shift to [off+1..off+deg]
    shift_gens := [];
    for g in GeneratorsOfGroup(G) do
        img := ListPerm(g, deg);
        full := [1..16];
        for j in [1..deg] do
            full[j + off] := img[j] + off;
        od;
        Add(shift_gens, PermList(full));
    od;
    Add(_shifted, Group(shift_gens));
    Add(_offs, off);
    off := off + deg;
od;
_P := Group(Concatenation(List(_shifted, GeneratorsOfGroup)));

Print("P = ", _P, "\\n");
Print("|P| = ", Size(_P), "\\n");
Print("IsAbelian(P) = ", IsAbelian(_P), "\\n");
Print("IsElementaryAbelian(P) = ", IsElementaryAbelian(_P), "\\n");

pcgs := Pcgs(_P);
Print("Length(Pcgs(P)) = ", Length(pcgs), "\\n");
Print("RelativeOrders = ", RelativeOrders(pcgs), "\\n");

# Build partition normalizer
N := BuildConjugacyTestGroup(16, partition);
Print("|N| = ", Size(N), "\\n");

# Now test the normalizer computation
Print("\\n=== Testing Normalizer(N, P) ===\\n");
actualNorm := Normalizer(N, _P);
Print("|Normalizer(N, P)| = ", Size(actualNorm), "\\n");

# Test SmallGeneratingSet
normGens := SmallGeneratingSet(actualNorm);
Print("SmallGeneratingSet: ", Length(normGens), " generators\\n");

# Test matrix computation
dim := Length(pcgs);
p := 2;
field := GF(p);
Print("\\n=== Testing matrix computation ===\\n");
for jj in [1..Length(normGens)] do
    Print("Generator ", jj, ": ", normGens[jj], "\\n");
    mat := [];
    for ii in [1..dim] do
        conj := pcgs[ii] ^ normGens[jj];
        Print("  pcgs[", ii, "] ^ gen = ", conj, "\\n");
        Print("  conj in P = ", conj in _P, "\\n");
        if conj in _P then
            exps := ExponentsOfPcElement(pcgs, conj);
            Print("  exps = ", exps, " (length ", Length(exps), ")\\n");
            Add(mat, List(exps, e -> (e mod p) * One(field)));
        else
            Print("  ERROR: conjugate not in P!\\n");
        fi;
    od;
    Print("  Matrix: ", mat, "\\n\\n");
od;

# Now test with a small number of FPF subgroups
Print("\\n=== Testing RREF conversion with trivial subgroup ===\\n");
H := Group(pcgs[1]);
Print("H = ", H, ", |H| = ", Size(H), "\\n");
gens_H := Pcgs(H);
if gens_H = fail then
    gens_H := GeneratorsOfGroup(H);
fi;
mat_H := List(gens_H, g ->
    List(ExponentsOfPcElement(pcgs, g), e -> (e mod p) * One(field)));
Print("mat_H = ", mat_H, "\\n");
semi := SemiEchelonMat(mat_H);
Print("semi.vectors = ", semi.vectors, "\\n");
Print("Row lengths: ", List(semi.vectors, Length), "\\n");

Print("\\n=== Now testing _DeduplicateEAFPFbyGF2Orbits with small input ===\\n");
# Create a few test subgroups
testSubs := [Group(pcgs[1], pcgs[2]), Group(pcgs[3], pcgs[4])];
Print("Test with ", Length(testSubs), " subgroups\\n");
result := _DeduplicateEAFPFbyGF2Orbits(_P, testSubs, N);
Print("Result: ", Length(result), " orbit reps\\n");

# Test 2: Same for [4,4,4,2,2]
Print("\\n\\n=== Test 2: [4,4,4,2,2] ===\\n");
partition2 := [4,4,4,2,2];
comboIndices2 := [[4,2],[4,2],[4,2],[2,1],[2,1]];

_shifted2 := [];
_offs2 := [];
off := 0;
for ci in comboIndices2 do
    deg := ci[1];
    idx := ci[2];
    G := TransitiveGroup(deg, idx);
    shift_gens := [];
    for g in GeneratorsOfGroup(G) do
        img := ListPerm(g, deg);
        full := [1..16];
        for j in [1..deg] do
            full[j + off] := img[j] + off;
        od;
        Add(shift_gens, PermList(full));
    od;
    Add(_shifted2, Group(shift_gens));
    Add(_offs2, off);
    off := off + deg;
od;
_P2 := Group(Concatenation(List(_shifted2, GeneratorsOfGroup)));
Print("|P2| = ", Size(_P2), "\\n");
Print("IsElementaryAbelian(P2) = ", IsElementaryAbelian(_P2), "\\n");

N2 := BuildConjugacyTestGroup(16, partition2);
Print("|N2| = ", Size(N2), "\\n");

actualNorm2 := Normalizer(N2, _P2);
Print("|Normalizer(N2, P2)| = ", Size(actualNorm2), "\\n");
normGens2 := SmallGeneratingSet(actualNorm2);
Print(Length(normGens2), " generators\\n");

pcgs2 := Pcgs(_P2);
dim2 := Length(pcgs2);
Print("dim2 = ", dim2, "\\n");

# Test matrix computation for partition 2
for jj in [1..Length(normGens2)] do
    Print("Gen ", jj, ":\\n");
    for ii in [1..dim2] do
        conj := pcgs2[ii] ^ normGens2[jj];
        if not conj in _P2 then
            Print("  ERROR: pcgs[", ii, "] conjugate not in P2!\\n");
        else
            exps := ExponentsOfPcElement(pcgs2, conj);
            if Length(exps) <> dim2 then
                Print("  ERROR: exps length ", Length(exps), " != dim ", dim2, "\\n");
            fi;
        fi;
    od;
    Print("  OK\\n");
od;

# Now try full dedup with small input
testSubs2 := [Group(pcgs2[1], pcgs2[2]), Group(pcgs2[3], pcgs2[4])];
result2 := _DeduplicateEAFPFbyGF2Orbits(_P2, testSubs2, N2);
Print("Result2: ", Length(result2), " orbit reps\\n");

Print("\\nAll tests passed!\\n");
LogTo();
QUIT;
'''

with open(os.path.join(BASE_DIR, "temp_commands.g"), "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running GF(2) dedup test (should be fast - no AllSubgroups)...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)
print(f"Exit code: {process.returncode}")
if stdout.strip():
    print(f"STDOUT:\n{stdout[:2000]}")
if stderr.strip():
    print(f"STDERR:\n{stderr[:2000]}")

if os.path.exists(os.path.join(BASE_DIR, "gap_output_gf2fix.log")):
    with open(os.path.join(BASE_DIR, "gap_output_gf2fix.log")) as f:
        log = f.read()
    print(f"\nLog ({len(log)} chars):")
    print(log)
