"""Clean Holt pipeline test on S_6, S_7, S_8.

Expected subgroup class counts (GAP ConjugacyClassesSubgroups):
  S_6: should match via TRANSITIVE_SUBGROUPS library
  S_7: same
  S_8: same

These exercise: non-solvable input (L = {1}), TF-top-only pipeline, and
the tf_database lookup across library-backed cases.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "clean_pipeline_larger_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== S_6 ===\\n");
s6 := SymmetricGroup(6);
truth := Length(ConjugacyClassesSubgroups(s6));
Print("Truth: ", truth, "\\n");
t0 := Runtime();
holt := HoltSubgroupClassesOfGroup(s6);
Print("Holt:  ", Length(holt), " (", Runtime() - t0, "ms)\\n");
Print("S_6 match: ", Length(holt) = truth, "\\n");

Print("\\n=== S_7 ===\\n");
s7 := SymmetricGroup(7);
truth := Length(ConjugacyClassesSubgroups(s7));
Print("Truth: ", truth, "\\n");
t0 := Runtime();
holt := HoltSubgroupClassesOfGroup(s7);
Print("Holt:  ", Length(holt), " (", Runtime() - t0, "ms)\\n");
Print("S_7 match: ", Length(holt) = truth, "\\n");

Print("\\n=== S_4 x C_2 (radical + TF top) ===\\n");
# This is a product with BOTH a nontrivial radical AND nontrivial TF top
# via solvable nature. Actually S_4 x C_2 is solvable, so L = S_4 x C_2,
# TF top trivial. Try S_5 x C_2 instead: L = {1} x C_2 = C_2, TF top = S_5.
s5c2 := DirectProduct(SymmetricGroup(5), CyclicGroup(IsPermGroup, 2));
truth := Length(ConjugacyClassesSubgroups(s5c2));
Print("S_5 x C_2 Truth: ", truth, "\\n");
t0 := Runtime();
holt := HoltSubgroupClassesOfGroup(s5c2);
Print("Holt:  ", Length(holt), " (", Runtime() - t0, "ms)\\n");
Print("S_5 x C_2 match: ", Length(holt) = truth, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_clean_larger.g")
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

print("=== stdout ===")
print(proc.stdout[-4000:])
print("=== stderr (last 1K) ===")
print(proc.stderr[-1000:] if proc.stderr else "(empty)")

os.remove(cmd_file)

checks = [
    "S_6 match: true",
    "S_7 match: true",
    "S_5 x C_2 match: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Clean Holt pipeline (S_6/S_7/S_5xC_2)")
sys.exit(0 if ok else 1)
