"""Diff-test HoltFPFSubgroupClassesOfProduct (FPF filter pushed into lift)
vs HoltCleanFPFSubgroupClasses (post-enumeration filter)
vs FindFPFClassesByLifting (legacy).

All three must agree on count for every tested combo.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "fpf_in_lift_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

TestCombo := function(name, t1, t2, offs)
  local t2shift, P, shifted, t0, r_in, r_post, r_leg;
  t2shift := Group(List(GeneratorsOfGroup(t2),
    g -> PermList(Concatenation([1..offs[2]],
                                List([1..NrMovedPoints(t2)],
                                     i -> offs[2] + i^g)))));
  P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2shift)));
  shifted := [t1, t2shift];

  FPF_SUBDIRECT_CACHE := rec();
  t0 := Runtime();
  r_in := HoltFPFSubgroupClassesOfProduct(P, shifted, offs);
  Print(name, " Holt in-lift:  ", Length(r_in), " (", Runtime()-t0, "ms)\\n");

  FPF_SUBDIRECT_CACHE := rec();
  t0 := Runtime();
  r_post := HoltCleanFPFSubgroupClasses(P, shifted, offs);
  Print(name, " Holt post-flt: ", Length(r_post), " (", Runtime()-t0, "ms)\\n");

  FPF_SUBDIRECT_CACHE := rec();
  t0 := Runtime();
  r_leg := FindFPFClassesByLifting(P, shifted, offs);
  Print(name, " Legacy:        ", Length(r_leg), " (", Runtime()-t0, "ms)\\n");

  Print(name, " match (all three): ",
        Length(r_in) = Length(r_post) and Length(r_post) = Length(r_leg), "\\n\\n");
end;

Print("=== [S_3, S_3] ===\\n");
TestCombo("[S_3,S_3]", SymmetricGroup(3), SymmetricGroup(3), [0, 3]);

Print("=== [T(4,3), T(2,1)] ===\\n");
TestCombo("[T(4,3),T(2,1)]", TransitiveGroup(4,3), TransitiveGroup(2,1), [0, 4]);

Print("=== [T(4,5)=S_4, T(3,2)=S_3] ===\\n");
TestCombo("[S_4,S_3]", TransitiveGroup(4,5), TransitiveGroup(3,2), [0, 4]);

Print("=== [T(5,3), T(4,3)] ===\\n");
TestCombo("[T(5,3),T(4,3)]", TransitiveGroup(5,3), TransitiveGroup(4,3), [0, 5]);

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_fpf_in_lift.g")
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
print(proc.stdout[-4000:])
os.remove(cmd_file)

matches = proc.stdout.count("match (all three): true")
ok = matches == 4
print(f"\n[{'PASS' if ok else 'FAIL'}] FPF-in-lift diff test ({matches}/4 combos match)")
sys.exit(0 if ok else 1)
