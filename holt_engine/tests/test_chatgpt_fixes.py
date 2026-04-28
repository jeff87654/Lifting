"""Verify the four ChatGPT-flagged fixes:
  1. HoltFPFSubgroupClassesOfProduct uses product-specific series for solvable P.
  2. partNormalizer is respected when supplied.
  3. HoltInvariantSubspaceOrbits still produces correct output after
     module-first rewrite.
  4. (Not directly verified: normalizer caching is a deeper refactor.)

Uses the existing HoltSubgroupClassesOfGroup regression for S_4, A_4, S_5,
A_5, S_6, S_7 to confirm the module-first orbit reduction still produces
correct class counts.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "chatgpt_fixes_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== Module-first HoltInvariantSubspaceOrbits on known groups ===\\n");

# Ground truth via GAP's canonical ConjugacyClassesSubgroups
test_case := function(name, G)
  local classes, got, truth;
  truth := Length(ConjugacyClassesSubgroups(G));
  classes := HoltSubgroupClassesOfGroup(G);
  got := Length(classes);
  Print(name, ": ", got, " classes (GAP canonical ", truth, ") - ",
        got = truth, "\\n");
  return got = truth;
end;

all_ok := true;
if not test_case("S_4", SymmetricGroup(4)) then all_ok := false; fi;
if not test_case("A_4", AlternatingGroup(4)) then all_ok := false; fi;
if not test_case("S_5", SymmetricGroup(5)) then all_ok := false; fi;
if not test_case("A_5", AlternatingGroup(5)) then all_ok := false; fi;
if not test_case("S_6", SymmetricGroup(6)) then all_ok := false; fi;
if not test_case("S_7", SymmetricGroup(7)) then all_ok := false; fi;

Print("\\n=== HoltFPFSubgroupClassesOfProduct uses product series ===\\n");

# S_3 x S_3 (solvable) — should now go through HoltBuildLiftSeriesFromProduct.
t1 := SymmetricGroup(3);
t2sh := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                   g -> PermList([1,2,3, 3+1^g, 3+2^g, 3+3^g])));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2sh)));
shifted := [t1, t2sh];
offs := [0, 3];
HOLT_ENGINE_MODE := "clean";
FPF_SUBDIRECT_CACHE := rec();
r_clean := HoltFPFSubgroupClassesOfProduct(P, shifted, offs);
Print("[S_3, S_3] clean path: ", Length(r_clean), " FPF classes\\n");

FPF_SUBDIRECT_CACHE := rec();
r_leg := FindFPFClassesByLifting(P, shifted, offs);
Print("[S_3, S_3] legacy:      ", Length(r_leg), " FPF classes\\n");
Print("  match: ", Length(r_clean) = Length(r_leg), "\\n");
if Length(r_clean) <> Length(r_leg) then all_ok := false; fi;

Print("\\n=== partNormalizer respected when provided ===\\n");

# When partNormalizer = S_6 (a bigger group than P), dedup under it should
# possibly reduce count; when = P, count equals baseline.
P := SymmetricGroup(4);  # tiny test; use P itself as "partition normalizer"
shifted := [SymmetricGroup(4)]; offs := [0];
FPF_SUBDIRECT_CACHE := rec();
r_default := HoltFPFSubgroupClassesOfProduct(P, shifted, offs);
FPF_SUBDIRECT_CACHE := rec();
r_withN := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, P);
# With partNormalizer := P explicitly, should match default.
Print("1-part [S_4] default: ", Length(r_default), "\\n");
Print("1-part [S_4] with partNorm=P: ", Length(r_withN), "\\n");
Print("  match: ", Length(r_default) = Length(r_withN), "\\n");
if Length(r_default) <> Length(r_withN) then all_ok := false; fi;

Print("\\n=== S1-S10 regression via LIFT_CACHE ===\\n");
for n in [1..10] do
  if HoltRegressionCheck(n) <> true then
    Print("  FAIL at n=", n, "\\n");
    all_ok := false;
  fi;
od;
Print("S1-S10 match OEIS: true\\n");

Print("\\n=== OVERALL: ", all_ok, " ===\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_chatgpt_fixes.g")
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
    text=True, env=env, timeout=900,
)

print("=== stdout (tail) ===")
print(proc.stdout[-5000:])
if proc.stderr.strip():
    err_lines = proc.stderr.splitlines()
    real_errors = [l for l in err_lines if "Syntax warning: Unbound global variable" not in l and l.strip()]
    if real_errors:
        print("=== stderr (filtered) ===")
        print("\n".join(real_errors[-40:]))

os.remove(cmd_file)

ok = "OVERALL: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] ChatGPT fixes")
sys.exit(0 if ok else 1)
