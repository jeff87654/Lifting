"""Verify holt_engine_monolith.g loads cleanly and exercises key functions."""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "monolith_load_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine_monolith.g");

Print("\\n=== HOLT_ENGINE_LOADED = ", HOLT_ENGINE_LOADED, " ===\\n");

# Sanity: all public Holt* names bound
names := [
  "HoltMakeClassRec", "HoltEmitHeartbeat", "HoltSaveCheckpoint",
  "HoltCheapSubgroupInvariant", "HoltBuildLiftSeries",
  "HoltInvariantSubspaces", "HoltInvariantSubspaceOrbits",
  "HoltRefineToElementaryAbelianLayers",
  "HoltComputeH1Action", "HoltPresentationForClassRec",
  "HoltLiftOneParentAcrossLayer", "HoltIdentifyTFTop",
  "HoltLoadTFClasses", "HoltFPFClassesForPartition",
  "HoltSubgroupClassesOfGroup", "HoltRegressionCheck"
];
ok := true;
for name in names do
  if not IsBoundGlobal(name) then
    Print("MISSING: ", name, "\\n");
    ok := false;
  fi;
od;
Print("All public names bound: ", ok, "\\n");

# Smoke test: refinement utility works end-to-end
s4 := SymmetricGroup(4);
v4 := Group([(1,2)(3,4), (1,3)(2,4)]);
triv := TrivialSubgroup(s4);
chain := HoltRefineToElementaryAbelianLayers(s4, triv, v4, 2);
Print("HoltRefineToElementaryAbelianLayers(S_4, 1, V_4, 2) sizes: ",
      List(chain, Size), " (expect [1, 4])\\n");

# Smoke test: HoltBuildLiftSeries on S_4
series := HoltBuildLiftSeries(s4);
Print("HoltBuildLiftSeries(S_4): |radical|=", Size(series.radical),
      ", layers=", Length(series.layers), "\\n");

# Smoke test: verify S_4 = 11 via the cached legacy path (monolith shouldn't
# have broken anything)
s4_count := CountAllConjugacyClassesFast(4);
Print("CountAllConjugacyClassesFast(4) = ", s4_count, " (expect 11)\\n");

Print("\\n=== MONOLITH LOAD: ", ok and s4_count = 11, " ===\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "temp_monolith_test.g")
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
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, timeout=300,
)

print("=== stdout (tail) ===")
print(proc.stdout[-3000:])

if proc.stderr.strip():
    # Show only non-trivial stderr (filter out pre-existing syntax warnings)
    err_lines = proc.stderr.splitlines()
    real_errors = [l for l in err_lines if "Syntax warning: Unbound global variable" not in l and l.strip()]
    if real_errors:
        print("=== stderr (filtered) ===")
        print("\n".join(real_errors[-30:]))

os.remove(cmd_file)

ok = "MONOLITH LOAD: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] Monolith load test")
sys.exit(0 if ok else 1)
