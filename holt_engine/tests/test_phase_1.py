"""Phase 1 test: HoltBuildLiftSeries + dedup_invariants wrappers.

Checks:
  S4: radical=V_4, 2 layers (C_2 inside V_4, then V_4/1), tf_top ≠ 1 — wait:
       S_4 has radical V_4; series 1 < V_4 < A_4 < S_4, so layers are
       {1 < C_2 < V_4} after refinement → 2 elementary abelian C_2 layers.
       tf_top = S_3.
  S5: radical=1, 0 layers, tf_top=S_5.
  A5×C2: radical=C_2, 1 layer, tf_top ≅ A_5.
  Invariants: HoltCheapSubgroupInvariant(H) equals CheapSubgroupInvariantFull(H).
  S1-S10 regression still passes (HoltRegressionCheck(n) for n in 1..10).
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_1_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== HoltBuildLiftSeries tests ===\\n");

# S_4 (fully solvable: derived series S_4 > A_4 > V_4 > 1)
s4 := SymmetricGroup(4);
r := HoltBuildLiftSeries(s4);
Print("S_4: radical size = ", Size(r.radical),
      " (expect 24 = S_4, it's solvable), layers = ", Length(r.layers),
      " (expect 3: C_2 sign, C_3 in A_4/V_4, V_4)\\n");
Print("  layer factor sizes: ",
      List(r.layers, l -> [l.p, l.d, l.p^l.d]), "\\n");

# S_5
s5 := SymmetricGroup(5);
r := HoltBuildLiftSeries(s5);
Print("S_5: radical size = ", Size(r.radical),
      " (expect 1), layers = ", Length(r.layers), "\\n");

# A_5 x C_2
a5c2 := DirectProduct(AlternatingGroup(5), CyclicGroup(IsPermGroup, 2));
r := HoltBuildLiftSeries(a5c2);
Print("A_5 x C_2: radical size = ", Size(r.radical),
      " (expect 2), layers = ", Length(r.layers), " (expect 1)\\n");

Print("\\n=== Product-series tests ===\\n");

# 2-factor product S_3 x S_3 properly embedded: factor 1 on {1,2,3},
# factor 2 on {4,5,6}
dp := DirectProduct(SymmetricGroup(3), SymmetricGroup(3));
emb1 := Embedding(dp, 1);
emb2 := Embedding(dp, 2);
shifted1 := Image(emb1, SymmetricGroup(3));
shifted2 := Image(emb2, SymmetricGroup(3));
factors := [shifted1, shifted2];
r := HoltBuildLiftSeriesFromProduct(dp, factors);
Print("S_3 x S_3 (properly shifted): layers = ", Length(r.layers),
      " (expect 4: two C_2 and two C_3)\\n");
Print("  layer factor sizes: ",
      List(r.layers, l -> [l.p, l.d, l.p^l.d]), "\\n");

Print("\\n=== dedup_invariants wrappers ===\\n");

# Ensure CURRENT_BLOCK_RANGES is defined (some existing call sites set it)
if not IsBound(CURRENT_BLOCK_RANGES) then CURRENT_BLOCK_RANGES := []; fi;

h1 := Group([(1,2,3,4),(1,3)]);  # D_8 inside S_4
inv_full := CheapSubgroupInvariantFull(h1);
inv_holt := HoltCheapSubgroupInvariant(h1);
Print("Invariant match (Cheap): ", inv_full = inv_holt, "\\n");

inv_exp := ExpensiveSubgroupInvariant(h1);
inv_hexp := HoltExpensiveSubgroupInvariant(h1);
Print("Invariant match (Expensive): ", inv_exp = inv_hexp, "\\n");

inv_comp := ComputeSubgroupInvariant(h1);
inv_hcomp := HoltComputeSubgroupInvariant(h1);
Print("Invariant match (Compute): ", inv_comp = inv_hcomp, "\\n");

key_a := InvariantKey(inv_comp);
key_b := HoltInvariantKey(inv_comp);
Print("Invariant key match: ", key_a = key_b, "\\n");

Print("Match check: ", HoltInvariantsMatch(inv_full, inv_holt), "\\n");

Print("\\n=== S1-S10 regression ===\\n");
pass := true;
for n in [1..10] do
  if HoltRegressionCheck(n) <> true then
    Print("  FAIL at n=", n, "\\n");
    pass := false;
  fi;
od;
Print("S1-S10 regression: ", pass, "\\n");

LogTo();
QUIT;
'''

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_1.g")
with open(cmd_file, "w") as f:
    f.write(gap_commands)

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)

proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    timeout=600,
)

print("=== stdout ===")
print(proc.stdout[-4000:])
print("=== stderr (last 2K) ===")
print(proc.stderr[-2000:] if proc.stderr else "(empty)")

if os.path.exists(LOG_FILE):
    print("=== GAP log ===")
    with open(LOG_FILE) as f:
        print(f.read())

os.remove(cmd_file)

checks = [
    "Invariant match (Cheap): true",
    "Invariant match (Expensive): true",
    "Invariant match (Compute): true",
    "Invariant key match: true",
    "S1-S10 regression: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 1 test")
sys.exit(0 if ok else 1)
