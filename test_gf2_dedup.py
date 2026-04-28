"""Test GF(2) post-lift dedup on [4,2]^4 x [2,1] combo (P = C_2^9).

Tests the new lifting + GF(2) post-lift dedup path.
W110 (running the old incrementalDedup path) provides ground truth.
"""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/test_gf2_dedup.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== TEST: GF(2) post-lift dedup on V_4^4 x C_2 (C_2^9) ===\\n\\n");

# Build the combo: [4,2]^4 x [2,1] for partition [4,4,4,4,2]
combo := [[4,2],[4,2],[4,2],[4,2],[2,1]];

# Build shifted factors
shifted := [];
offs := [];
pos := 0;
for c in combo do
    G := TransitiveGroup(c[1], c[2]);
    Add(shifted, ShiftGroup(G, pos));
    Add(offs, pos);
    pos := pos + c[1];
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), "\\n");
Print("IsElementaryAbelian(P) = ", IsElementaryAbelian(P), "\\n\\n");

# Build partition normalizer for this combo
normGens := [];
for i in [1..Length(shifted)] do
    N_i := Normalizer(SymmetricGroup([offs[i]+1..offs[i]+combo[i][1]]), shifted[i]);
    Append(normGens, GeneratorsOfGroup(N_i));
od;
# Add block-swap generators for identical factors
for i in [1..Length(combo)-1] do
    for j in [i+1..Length(combo)] do
        if combo[i] = combo[j] then
            swapPerm := ();
            for k in [1..combo[i][1]] do
                swapPerm := swapPerm * (offs[i]+k, offs[j]+k);
            od;
            Add(normGens, swapPerm);
        fi;
    od;
od;
partNorm := Group(normGens);
Print("|partNorm| = ", Size(partNorm), "\\n\\n");

# === Lifting with GF(2) post-lift dedup ===
Print("=== Lifting + GF(2) post-lift dedup ===\\n");
t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, partNorm);
tLift := Runtime() - t0;
Print("\\nResult: ", Length(result), " N-orbit reps in ", tLift, "ms (",
      Int(tLift/1000), "s)\\n");

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "test_gf2_dedup.g")
with open(script_file, "w") as f:
    f.write(gap_commands)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_gf2_dedup.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Launching GF(2) dedup test...")
t0 = time.time()

process = subprocess.Popen(
    [BASH_EXE, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     f'exec ./gap.exe -q -o 0 "{script_cygwin}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=7200)
elapsed = time.time() - t0
print(f"Completed in {elapsed:.0f}s (rc={process.returncode})")

log_path = log_file.replace("/", "\\")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    print("\n" + log[-3000:])
else:
    print("No log file found")
    print("stdout:", stdout[-1000:])
