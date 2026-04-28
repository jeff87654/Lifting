"""
S16: Compute the all-elementary-abelian combos that need GF(2) BFS orbit dedup.
These are the C2^8 combos that errored in W72 due to the immutable string bug.

Partitions with all-EA combos giving C2^8:
  [4,4,4,4]:       V4^4 = C2^8
  [4,2,2,2,2,2,2]: V4 x C2^6 = C2^8

This worker computes FindFPFClassesByLifting for just these specific combos
using the fixed BFS code (ShallowCopy string keys, memory optimization).
"""

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

wid = 73
results_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_results.txt"
hb_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_heartbeat.txt"

# GAP code to compute just the all-V4 combos using FindFPFClassesByLifting directly
gap_code = f'''
LogTo("C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}.log");
Print("Worker {wid} (BFS ShallowCopy fix) starting at ", Runtime()/1000, "s\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{hb_path}";

# =====================================================
# Combo 1: [4,4,4,4] all-V4: V4^4 = C2^8
# =====================================================
Print("\\n=== [4,4,4,4] all-V4 combo (C2^8) ===\\n");
PrintTo("{hb_path}", "computing [4,4,4,4] all-V4\\n");

t0 := Runtime();

# Build shifted V4 factors using ShiftGroup (from lifting_method_fast_v2.g)
shifted_4444 := [];
offs_4444 := [];
_off := 0;
for _k in [1..4] do
    Add(offs_4444, _off);
    Add(shifted_4444, ShiftGroup(TransitiveGroup(4, 2), _off));
    _off := _off + 4;
od;

# Build P as the direct product
P_4444 := Group(Concatenation(List(shifted_4444, GeneratorsOfGroup)));

# Build partition normalizer using BuildConjugacyTestGroup
N_4444 := BuildConjugacyTestGroup(16, [4,4,4,4]);

Print("  P = ", StructureDescription(P_4444), ", |P| = ", Size(P_4444), "\\n");
Print("  |N| = ", Size(N_4444), "\\n");

# Call FindFPFClassesByLifting - this will use SmallGroup fast path + BFS dedup
fpf_4444 := FindFPFClassesByLifting(P_4444, shifted_4444, offs_4444, N_4444);

elapsed := Runtime() - t0;
Print("[4,4,4,4] all-V4: ", Length(fpf_4444), " FPF classes (", elapsed, "ms)\\n");
AppendTo("{results_path}", "[4,4,4,4] all-V4: ", Length(fpf_4444), " classes (", elapsed, "ms)\\n");

# Save generators for later assembly
_outFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_bfs_4_4_4_4_allV4.txt";
PrintTo(_outFile, "");
for _g in fpf_4444 do
    AppendTo(_outFile, GeneratorsOfGroup(_g), "\\n");
od;
Print("Saved ", Length(fpf_4444), " generators to gens_bfs_4_4_4_4_allV4.txt\\n");

# =====================================================
# Combo 2: [4,2,2,2,2,2,2] all-V4: V4 x C2^6 = C2^8
# =====================================================
Print("\\n=== [4,2,2,2,2,2,2] all-V4 combo (C2^8) ===\\n");
PrintTo("{hb_path}", "computing [4,2,2,2,2,2,2] all-V4\\n");

t0 := Runtime();

# Build shifted factors: V4 on {{1..4}}, then C2 on {{5,6}}, {{7,8}}, ..., {{15,16}}
shifted_4222222 := [];
offs_4222222 := [];
_off := 0;

# First factor: V4 = TransitiveGroup(4, 2) on {{1..4}}
Add(offs_4222222, _off);
Add(shifted_4222222, ShiftGroup(TransitiveGroup(4, 2), _off));
_off := _off + 4;

# Six C2 factors on pairs
for _k in [1..6] do
    Add(offs_4222222, _off);
    Add(shifted_4222222, ShiftGroup(TransitiveGroup(2, 1), _off));
    _off := _off + 2;
od;

# Build P as the direct product
P_4222222 := Group(Concatenation(List(shifted_4222222, GeneratorsOfGroup)));

# Build partition normalizer
N_4222222 := BuildConjugacyTestGroup(16, [4,2,2,2,2,2,2]);

Print("  P = ", StructureDescription(P_4222222), ", |P| = ", Size(P_4222222), "\\n");
Print("  |N| = ", Size(N_4222222), "\\n");

# Call FindFPFClassesByLifting
fpf_4222222 := FindFPFClassesByLifting(P_4222222, shifted_4222222, offs_4222222, N_4222222);

elapsed := Runtime() - t0;
Print("[4,2,2,2,2,2,2] all-V4: ", Length(fpf_4222222), " FPF classes (", elapsed, "ms)\\n");
AppendTo("{results_path}", "[4,2,2,2,2,2,2] all-V4: ", Length(fpf_4222222), " classes (", elapsed, "ms)\\n");

# Save generators
_outFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_bfs_4_2_2_2_2_2_2_allV4.txt";
PrintTo(_outFile, "");
for _g in fpf_4222222 do
    AppendTo(_outFile, GeneratorsOfGroup(_g), "\\n");
od;
Print("Saved ", Length(fpf_4222222), " generators to gens_bfs_4_2_2_2_2_2_2_allV4.txt\\n");

PrintTo("{hb_path}", "ALL DONE\\n");
Print("\\nWorker {wid} ALL DONE\\n");
LogTo();
QUIT;
'''

os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "gens"), exist_ok=True)

script_file = os.path.join(LIFTING_DIR, f"temp_worker_{wid}.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_worker_{wid}.g"
log_file = os.path.join(OUTPUT_DIR, f"worker_{wid}.log")

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     f'./gap.exe -q -o 12g "{script_path}" 2>&1'],
    stdout=open(log_file, "w"),
    stderr=subprocess.STDOUT,
    env=env,
    cwd=gap_runtime
)
print(f"Launched W{wid}: BFS combos (PID {proc.pid})")
