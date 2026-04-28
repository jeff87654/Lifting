"""Dispatcher with pre-check + max-recursion fallback (no legacy).

Verifies:
  1. Small-TF combos: clean pipeline path (matches legacy count)
  2. Medium-TF combos: max-recursion path (matches legacy count)
  3. End-to-end S_7 via dispatcher: total = 96
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "dispatcher_maxrec_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_TF_STRICT_MISS := false;
HOLT_TF_CCS_DIRECT := 1000;
# HOLT_TF_MAXREC_CEILING unbound -> no ceiling
HOLT_PRECHECK_TFTHRESHOLD := 100;  # small so most combos go max-rec

Print("\\n=== Combo [S_3, S_3] (small TF top) ===\\n");
t1 := SymmetricGroup(3);
t2sh := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                   g -> PermList([1,2,3, 3+1^g, 3+2^g, 3+3^g])));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2sh)));
shifted := [t1, t2sh]; offs := [0, 3];
t0 := Runtime();
r_disp := _HoltDispatchLift(P, shifted, offs);
Print("Dispatch: ", Length(r_disp), " (", Runtime()-t0, "ms)\\n");
FPF_SUBDIRECT_CACHE := rec();
r_leg := FindFPFClassesByLifting(P, shifted, offs);
Print("Legacy:   ", Length(r_leg), "\\n");
Print("Match: ", Length(r_disp) = Length(r_leg), "\\n");

Print("\\n=== Combo [A_5, A_3] (TF top sizes 60*3 = 180, exercises max-rec) ===\\n");
t1 := AlternatingGroup(5);
t2 := AlternatingGroup(3);
t2sh := Group(List(GeneratorsOfGroup(t2),
                   g -> PermList(Concatenation([1..5],
                        List([1..3], i -> 5 + i^g)))));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2sh)));
shifted := [t1, t2sh]; offs := [0, 5];
Print("|P|=", Size(P), ", TF top size ~", Size(P)/Size(RadicalGroup(P)), "\\n");
t0 := Runtime();
r_disp := _HoltDispatchLift(P, shifted, offs);
Print("Dispatch: ", Length(r_disp), " (", Runtime()-t0, "ms)\\n");
FPF_SUBDIRECT_CACHE := rec();
r_leg := FindFPFClassesByLifting(P, shifted, offs);
Print("Legacy:   ", Length(r_leg), "\\n");
Print("Match: ", Length(r_disp) = Length(r_leg), "\\n");

Print("\\n=== End-to-end: S_7 via dispatcher ===\\n");
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
s7 := CountAllConjugacyClassesFast(7);
Print("S_7 = ", s7, " (", Int((Runtime()-t0)/1000), "s)\\n");
Print("S_7 match: ", s7 = 96, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_disp_maxrec.g")
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

print("=== stdout (last 4K) ===")
print(proc.stdout[-4000:])
os.remove(cmd_file)

matches = proc.stdout.count("Match: true") + proc.stdout.count("S_7 match: true")
ok = matches >= 3
print(f"\n[{'PASS' if ok else 'FAIL'}] Dispatcher + max-recursion ({matches}/3)")
sys.exit(0 if ok else 1)
