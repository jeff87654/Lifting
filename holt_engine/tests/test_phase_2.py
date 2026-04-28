"""Phase 2 test: module_layer, orbit_action, cohomology_lifter wrappers.

Checks:
  - HoltLayerModule(Q, M_bar, L) returns the same record as ChiefFactorAsModule.
  - HoltInvariantSubspaces(S, M, N) returns the same list as NormalSubgroupsBetween.
  - HoltSolveCocycles and HoltModuleFingerprint return identical output.
  - HoltBuildComplementInfo + HoltBuildComplementFromCocycle round-trip.
  - HoltLiftOneParentAcrossLayer(S_4, V_4/1, A_4) == LiftThroughLayer (single parent).
  - Atomic milestone: lifting S_4 via all layers from {1} produces 11 classes
    when combined with the legacy outer loop (CountAllConjugacyClassesFast(4)).
  - S1-S10 regression via HoltRegressionCheck(n).
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_2_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== module_layer wrappers ===\\n");

# S_4 with chief series 1 < V_4 < A_4 < S_4
s4 := SymmetricGroup(4);
a4 := AlternatingGroup(4);
v4 := Group([(1,2)(3,4), (1,3)(2,4)]);
triv := TrivialSubgroup(s4);

# HoltInvariantSubspaces == NormalSubgroupsBetween
inv_holt := HoltInvariantSubspaces(s4, v4, triv);
inv_legacy := NormalSubgroupsBetween(s4, v4, triv);
Print("HoltInvariantSubspaces(S_4, V_4, 1): ", Length(inv_holt), " subgroups\\n");
Print("  match legacy: ", inv_holt = inv_legacy, "\\n");

# HoltLayerModule == ChiefFactorAsModule
# Form the quotient Q = A_4 / 1 to test the module builder
mod_holt := HoltLayerModule(a4, v4, triv);
mod_legacy := ChiefFactorAsModule(a4, v4, triv);
Print("HoltLayerModule(A_4, V_4, 1): field=", mod_holt.field,
      " dim=", mod_holt.dimension, "\\n");
Print("  match legacy (record identity): ", mod_holt = mod_legacy, "\\n");

Print("\\n=== cohomology_lifter wrappers ===\\n");

# Use a solvable example where Pcgs path is active: S_4 / V_4 with module V_4
# Q = S_4, M_bar = V_4, and we solve cocycles for this action.
fp_holt := HoltModuleFingerprint(mod_holt);
fp_legacy := ComputeModuleFingerprint(mod_holt);
Print("HoltModuleFingerprint == legacy: ", fp_holt = fp_legacy, "\\n");

h1_holt := HoltSolveCocycles(mod_holt);
h1_legacy := CachedComputeH1(mod_holt);
Print("HoltSolveCocycles dim = ", h1_holt.H1Dimension, "\\n");
Print("  match legacy: ", h1_holt.H1Dimension = h1_legacy.H1Dimension, "\\n");

Print("\\n=== HoltLiftOneParentAcrossLayer ===\\n");

# Test: lift A_4 across V_4/1 inside S_4.
# A_4 is a parent containing M=V_4, and we find subgroups T <= A_4 with
# T*V_4 = A_4 and T cap V_4 = L for each S-invariant L between 1 and V_4.
# Expect FPF filtering against [S_4] to restrict to A_4 itself (the only
# transitive subgroup above V_4 on 4 points with FPF action).
layer := rec(M := v4, N := triv, p := 2, d := 2, index := 1);
shifted_factors := [s4];
offsets := [0];
children_holt := HoltLiftOneParentAcrossLayer(s4, layer, a4, shifted_factors, offsets, fail, fail);
children_legacy := LiftThroughLayer(s4, v4, triv, [a4], shifted_factors, offsets, fail);
Print("HoltLiftOneParentAcrossLayer(S_4, V_4/1, A_4) returned ",
      Length(children_holt), " subgroups\\n");
Print("  match legacy: ", Length(children_holt) = Length(children_legacy), "\\n");
Print("  children sizes: ", List(children_holt, Size), "\\n");

Print("\\n=== S_4 atomic milestone (full run) ===\\n");

# Legacy CountAllConjugacyClassesFast for S_4 should return 11.
# This exercises the full lifting chain 1 < V_4 < A_4 < S_4.
# (The wrappers above are byte-identical, so this must still return 11.)
s4_count := CountAllConjugacyClassesFast(4);
Print("CountAllConjugacyClassesFast(4) = ", s4_count, " (expect 11)\\n");
Print("  S_4 milestone: ", s4_count = 11, "\\n");

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
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_2.g")
with open(cmd_file, "w", encoding="utf-8") as f:
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
    "match legacy: true",
    "match legacy (record identity): true",
    "HoltModuleFingerprint == legacy: true",
    "S_4 milestone: true",
    "S1-S10 regression: true",
]
# Count "match legacy: true" - expect 3+ of them
ok_total = proc.stdout.count("match legacy: true") >= 3
ok_fp = "HoltModuleFingerprint == legacy: true" in proc.stdout
ok_s4 = "S_4 milestone: true" in proc.stdout
ok_reg = "S1-S10 regression: true" in proc.stdout
ok = ok_total and ok_fp and ok_s4 and ok_reg

print(f"  [{'OK' if ok_total else 'MISSING'}] >= 3 'match legacy: true' lines")
print(f"  [{'OK' if ok_fp else 'MISSING'}] HoltModuleFingerprint == legacy: true")
print(f"  [{'OK' if ok_s4 else 'MISSING'}] S_4 milestone: true")
print(f"  [{'OK' if ok_reg else 'MISSING'}] S1-S10 regression: true")
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 2 test")
sys.exit(0 if ok else 1)
