"""
Detailed trace: which cocycle vectors map to FPF complements?
For [T6_2, T6_2, T3_1], parent 2.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/trace_orbital2.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T62 := TransitiveGroup(6, 2);
T31 := TransitiveGroup(3, 1);
factors := [T62, T62, T31];
shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
N := BuildConjugacyTestGroup(15, [6, 6, 3]);
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

series := RefinedChiefSeries(P);
parents := [P];
for i in [1..Length(series)-2] do
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;

M := series[Length(series)-1];
L := series[Length(series)];

S := parents[2];  # The parent with H1 dim = 1
hom := NaturalHomomorphismByNormalSubgroup(S, L);
Q := ImagesSource(hom);
M_bar := Image(hom, M);
module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
ClearH1Cache();
H1 := CachedComputeH1(module);

Print("H1 dim = ", H1.H1Dimension, " p = ", module.p, "\\n");
Print("Module generators: ", module.generators, "\\n");
Print("Module preimageGens: ", module.preimageGens, "\\n");
Print("quotientBasis: ", H1.quotientBasis, "\\n");
Print("coboundaryBasis: ", H1.coboundaryBasis, "\\n\\n");

# Enumerate all 3 cocycle vectors and their complements
complementInfo := BuildComplementInfo(Q, M_bar, module);

Print("=== All cocycles and complements ===\\n");
for c in [0, 1, 2] do
    h1_coords := [c * One(GF(3))];
    fullCocycle := H1CoordsToFullCocycle(H1, h1_coords);
    C := CocycleToComplement(fullCocycle, complementInfo);
    C_lifted := PreImages(hom, C);
    is_fpf := IsFPFSubdirect(C_lifted, shifted, offs);
    Print("Cocycle ", c, ": coords=", h1_coords, " fullCocycle=", fullCocycle,
          " |C|=", Size(C), " |C_lifted|=", Size(C_lifted),
          " FPF=", is_fpf, "\\n");
    Print("  C gens: ", GeneratorsOfGroup(C), "\\n");
    Print("  C_lifted gens: ", GeneratorsOfGroup(C_lifted), "\\n");
od;

# Check P-conjugacy between all pairs
Print("\\n=== P-conjugacy between lifted complements ===\\n");
for c1 in [0, 1, 2] do
    for c2 in [c1+1..2] do
        h1_1 := [c1 * One(GF(3))];
        h1_2 := [c2 * One(GF(3))];
        C1 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_1), complementInfo);
        C2 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_2), complementInfo);
        C1_lifted := PreImages(hom, C1);
        C2_lifted := PreImages(hom, C2);

        # Check P-conjugacy
        x := RepresentativeAction(P, C1_lifted, C2_lifted);
        Print("Cocycles ", c1, " vs ", c2, ": P-conj=", x <> fail, "\\n");
    od;
od;

# Check N-conjugacy
Print("\\n=== N-conjugacy between lifted complements ===\\n");
for c1 in [0, 1, 2] do
    for c2 in [c1+1..2] do
        h1_1 := [c1 * One(GF(3))];
        h1_2 := [c2 * One(GF(3))];
        C1 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_1), complementInfo);
        C2 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_2), complementInfo);
        C1_lifted := PreImages(hom, C1);
        C2_lifted := PreImages(hom, C2);

        x := RepresentativeAction(N, C1_lifted, C2_lifted);
        Print("Cocycles ", c1, " vs ", c2, ": N-conj=", x <> fail, "\\n");
    od;
od;

# Outer normalizer
N_S := Normalizer(P, S);
N_M := Normalizer(P, M);
outerNorm := Intersection(N_S, N_M);
Print("\\n|N_P(S)|=", Size(N_S), " |N_P(M)|=", Size(N_M),
      " |outerNorm|=", Size(outerNorm), " |S|=", Size(S), "\\n");
outerNormGens := [];
for gen in GeneratorsOfGroup(outerNorm) do
    if not gen in S then
        if not ForAll(GeneratorsOfGroup(S), s -> s^gen = s) then
            Add(outerNormGens, gen);
        fi;
    fi;
od;
Print("outerNormGens: ", outerNormGens, "\\n");

# Action matrix
H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, hom, P);
Print("Action matrices: ", H1action.matrices, "\\n\\n");

# Verify the action manually:
# Apply n to cocycle 1 and cocycle 2
for n in outerNormGens do
    Print("Outer normalizer gen: ", n, "\\n");
    for c in [0, 1, 2] do
        h1_coords := [c * One(GF(3))];
        fullCocycle := H1CoordsToFullCocycle(H1, h1_coords);
        C := CocycleToComplement(fullCocycle, complementInfo);
        C_lifted := PreImages(hom, C);

        # Conjugate by n
        C_conj := C_lifted^n;
        # Find which cocycle this corresponds to
        for c2 in [0, 1, 2] do
            h1_2 := [c2 * One(GF(3))];
            C2 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_2), complementInfo);
            C2_lifted := PreImages(hom, C2);
            if C_conj = C2_lifted then
                Print("  n maps cocycle ", c, " to cocycle ", c2, "\\n");
                break;
            fi;
        od;
        # If not found, check S-conjugacy
        for c2 in [0, 1, 2] do
            h1_2 := [c2 * One(GF(3))];
            C2 := CocycleToComplement(H1CoordsToFullCocycle(H1, h1_2), complementInfo);
            C2_lifted := PreImages(hom, C2);
            if RepresentativeAction(S, C_conj, C2_lifted) <> fail then
                Print("  n maps cocycle ", c, " to S-conjugate of cocycle ", c2, "\\n");
                break;
            fi;
        od;
    od;
    Print("\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_trace_orbital2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_trace_orbital2.g"

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

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    # Print all non-trivially-long lines
    for line in log.split('\n'):
        line = line.strip()
        if line and not line.startswith('Syntax') and not line.startswith('#') and len(line) > 3:
            print(line)
except FileNotFoundError:
    print("Log file not found!")
