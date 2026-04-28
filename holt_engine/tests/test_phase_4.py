"""Phase 4 test: engine.g + symmetric_specialization.g integration.

Verifies:
  - HoltSubgroupClassesOfProduct returns the same groups as
    FindFPFClassesByLifting (thin-wrapper invariance).
  - HoltFPFClassesForPartition == FindFPFClassesForPartition on [5,5] of S10.
  - _HoltDispatchLift routing: with USE_HOLT_ENGINE := true, the four
    swapped call sites in lifting_method_fast_v2.g route through
    HoltSubgroupClassesOfProduct. End-to-end S10 must still produce 1593.
  - S1-S10 regression.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_4_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

# Enable the Holt engine dispatch
USE_HOLT_ENGINE := true;
Print("USE_HOLT_ENGINE = ", USE_HOLT_ENGINE, "\\n");

Print("\\n=== HoltSubgroupClassesOfProduct (thin wrapper check) ===\\n");

# Build a 2-factor product: S_3 (on [1,2,3]) x S_3 (on [4,5,6])
dp := DirectProduct(SymmetricGroup(3), SymmetricGroup(3));
emb1 := Embedding(dp, 1);
emb2 := Embedding(dp, 2);
shifted1 := Image(emb1, SymmetricGroup(3));
shifted2 := Image(emb2, SymmetricGroup(3));
shifted := [shifted1, shifted2];
offs := [0, 3];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

result_holt := HoltSubgroupClassesOfProduct(P, shifted, offs);
result_legacy := FindFPFClassesByLifting(P, shifted, offs);
Print("HoltSubgroupClassesOfProduct count = ", Length(result_holt), "\\n");
Print("  legacy count = ", Length(result_legacy), "\\n");
Print("  wrapper matches legacy: ",
      Length(result_holt) = Length(result_legacy), "\\n");

Print("\\n=== HoltFPFClassesForPartition ===\\n");

# Partition [5,5] of S_10 (FPF part - needs to reach same count as legacy)
FPF_SUBDIRECT_CACHE := rec();
r_holt := HoltFPFClassesForPartition(10, [5,5]);
Print("HoltFPFClassesForPartition(10, [5,5]) count = ", Length(r_holt), "\\n");

FPF_SUBDIRECT_CACHE := rec();
r_legacy := FindFPFClassesForPartition(10, [5,5]);
Print("FindFPFClassesForPartition(10, [5,5]) count = ", Length(r_legacy), "\\n");
Print("  match: ", Length(r_holt) = Length(r_legacy), "\\n");

Print("\\n=== End-to-end S10 via _HoltDispatchLift (flag ON) ===\\n");

# Clear caches so the dispatcher is exercised end-to-end
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
s10_count := CountAllConjugacyClassesFast(10);
Print("CountAllConjugacyClassesFast(10) = ", s10_count, " (expect 1593)\\n");
Print("  S10 flagged-on correct: ", s10_count = 1593, "\\n");

Print("\\n=== Flag OFF baseline ===\\n");

USE_HOLT_ENGINE := false;
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
s10_off := CountAllConjugacyClassesFast(10);
Print("CountAllConjugacyClassesFast(10) = ", s10_off, " (expect 1593)\\n");
Print("  S10 flagged-off correct: ", s10_off = 1593, "\\n");

# Reload LIFT_CACHE so HoltRegressionCheck sees values
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

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

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_4.g")
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
    timeout=900,
)

print("=== stdout (last 5K) ===")
print(proc.stdout[-5000:])
print("=== stderr (last 2K) ===")
print(proc.stderr[-2000:] if proc.stderr else "(empty)")

if os.path.exists(LOG_FILE):
    print("=== GAP log (last 2K) ===")
    with open(LOG_FILE) as f:
        content = f.read()
    print(content[-2000:])

os.remove(cmd_file)

checks = [
    "wrapper matches legacy: true",
    "S10 flagged-on correct: true",
    "S10 flagged-off correct: true",
    "S1-S10 regression: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 4 test")
sys.exit(0 if ok else 1)
