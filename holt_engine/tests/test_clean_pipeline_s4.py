"""Clean Holt pipeline test: HoltSubgroupClassesOfGroup on small groups.

Implements holt_clean_architecture.md §5 end-to-end (no FPF filter, no
symmetric-specialization). This is the real pipeline: BuildLiftSeries ->
TF database -> layer-by-layer lift with orbit reduction on subspaces (§4.3)
and H^1 (§4.5).

Expected counts (GAP ConjugacyClassesSubgroups, verified):
  S_4 = 11, A_4 = 10, S_5 = 19, A_5 = 9
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "clean_pipeline_s4_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== Ground truth via GAP ConjugacyClassesSubgroups ===\\n");

s4 := SymmetricGroup(4);
a4 := AlternatingGroup(4);
s5 := SymmetricGroup(5);
a5 := AlternatingGroup(5);

truth_s4 := Length(ConjugacyClassesSubgroups(s4));
truth_a4 := Length(ConjugacyClassesSubgroups(a4));
truth_s5 := Length(ConjugacyClassesSubgroups(s5));
truth_a5 := Length(ConjugacyClassesSubgroups(a5));
Print("S_4: ", truth_s4, "\\n");
Print("A_4: ", truth_a4, "\\n");
Print("S_5: ", truth_s5, "\\n");
Print("A_5: ", truth_a5, "\\n");

Print("\\n=== HoltSubgroupClassesOfGroup (clean pipeline) ===\\n");

holt_s4 := HoltSubgroupClassesOfGroup(s4);
Print("S_4 via Holt: ", Length(holt_s4), " (expect ", truth_s4, ")\\n");
Print("  S_4 sizes sorted: ", SortedList(List(holt_s4, Size)), "\\n");
Print("  S_4 match: ", Length(holt_s4) = truth_s4, "\\n");

holt_a4 := HoltSubgroupClassesOfGroup(a4);
Print("A_4 via Holt: ", Length(holt_a4), " (expect ", truth_a4, ")\\n");
Print("  A_4 sizes sorted: ", SortedList(List(holt_a4, Size)), "\\n");
Print("  A_4 match: ", Length(holt_a4) = truth_a4, "\\n");

holt_a5 := HoltSubgroupClassesOfGroup(a5);
Print("A_5 via Holt: ", Length(holt_a5), " (expect ", truth_a5, ")\\n");
Print("  A_5 sizes sorted: ", SortedList(List(holt_a5, Size)), "\\n");
Print("  A_5 match: ", Length(holt_a5) = truth_a5, "\\n");

holt_s5 := HoltSubgroupClassesOfGroup(s5);
Print("S_5 via Holt: ", Length(holt_s5), " (expect ", truth_s5, ")\\n");
Print("  S_5 sizes sorted: ", SortedList(List(holt_s5, Size)), "\\n");
Print("  S_5 match: ", Length(holt_s5) = truth_s5, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_clean_s4.g")
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
    text=True, env=env, timeout=600,
)

print("=== stdout ===")
print(proc.stdout[-5000:])
print("=== stderr (last 2K) ===")
print(proc.stderr[-2000:] if proc.stderr else "(empty)")

os.remove(cmd_file)

checks = [
    "S_4 match: true",
    "A_4 match: true",
    "A_5 match: true",
    "S_5 match: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Clean Holt pipeline S_4/A_4/S_5/A_5")
sys.exit(0 if ok else 1)
