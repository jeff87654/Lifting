"""Test maximal-subgroup recursion for large TF tops.

Scenarios:
  1. A_8 (|G|=20160, ~137 subgroup classes): verify recursive path matches
     direct CCS count. This is the canonical case Holt's paper targets.
  2. S_8 (|G|=40320, ~296 subgroup classes): similar.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "max_recursion_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

HOLT_TF_CACHE := rec();
HOLT_TF_STRICT_MISS := false;
# Lower the CCS-direct threshold so A_8 exercises the recursive path
HOLT_TF_CCS_DIRECT := 1000;
HOLT_TF_MAXREC_CEILING := 100000;

Print("\\n=== Test A_8 subgroup classes via maximal recursion ===\\n");
a8 := AlternatingGroup(8);
Print("|A_8| = ", Size(a8), "\\n");

# Ground truth: direct CCS
Print("Computing truth via CCS...\\n");
t0 := Runtime();
truth := List(ConjugacyClassesSubgroups(a8), Representative);
t_truth := Runtime() - t0;
Print("Truth: ", Length(truth), " classes (", Int(t_truth/1000), "s)\\n");

# Direct call to HoltSubgroupsViaMaximals on a8 -- tests the recursion
# without going through HoltLoadTFClasses' cache chain.
HOLT_TF_CACHE := rec();
Print("\\nDirect call to HoltSubgroupsViaMaximals(a8)...\\n");
t0 := Runtime();
recursive := HoltSubgroupsViaMaximals(a8);
t_rec := Runtime() - t0;
Print("Recursive: ", Length(recursive), " classes (",
      Int(t_rec/1000), "s)\\n");

Print("Truth size distribution: ",
      Collected(SortedList(List(truth, Size))), "\\n");
Print("Recur size distribution: ",
      Collected(SortedList(List(recursive, Size))), "\\n");

Print("Counts match: ", Length(recursive) = Length(truth), "\\n");

LogTo();
QUIT;
'''

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_max_rec.g")
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
print(proc.stdout[-3000:])
os.remove(cmd_file)

ok = "Counts match: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] Maximal-subgroup recursion on A_8")
sys.exit(0 if ok else 1)
