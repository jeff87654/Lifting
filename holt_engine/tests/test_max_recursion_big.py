"""Probe: how feasible is MaximalSubgroupClassReps on A_8 x A_8 and friends?

If this is tractable, the max-recursion path can replace legacy fallback
for arbitrarily large TF tops.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "max_rec_big_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");

Print("\\n=== Probe 1: MaximalSubgroupClassReps on A_8 ===\\n");
a8 := AlternatingGroup(8);
Print("|A_8| = ", Size(a8), "\\n");
t0 := Runtime();
msr := ConjugacyClassesMaximalSubgroups(a8);
Print("ccmsubs count = ", Length(msr),
      " in ", Int((Runtime()-t0)/1000), "s, sizes = ",
      List(msr, c -> Size(Representative(c))), "\\n");

Print("\\n=== Probe 2: MaximalSubgroupClassReps on A_8 x A_8 ===\\n");
a82 := DirectProduct(a8, a8);
Print("|A_8 x A_8| = ", Size(a82), "\\n");
t0 := Runtime();
msr := ConjugacyClassesMaximalSubgroups(a82);
Print("ccmsubs count = ", Length(msr),
      " in ", Int((Runtime()-t0)/1000), "s\\n");
Print("sizes = ", List(msr, c -> Size(Representative(c))), "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_maxrec_big.g")
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
    text=True, env=env, timeout=1200,
)

print("=== stdout ===")
print(proc.stdout[-3000:])
os.remove(cmd_file)
