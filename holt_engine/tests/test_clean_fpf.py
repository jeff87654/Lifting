"""Clean Holt FPF pipeline test: HoltCleanFPFSubgroupClasses vs
FindFPFClassesByLifting on small S_n partition combos.

Tests: for each combo of transitive factors (T_1, ..., T_k) on disjoint
blocks, the clean Holt pipeline followed by an IsFPFSubdirect filter must
return the same number of classes as the legacy FPF-aware lifter.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "clean_fpf_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

# Case 1: partition [3,3] of S_6 with factors [S_3, S_3]
Print("\\n=== [S_3, S_3] on {{1,2,3}} x {{4,5,6}} ===\\n");
t1 := SymmetricGroup(3);
t2shift := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                      g -> PermList([1, 2, 3, 3+1^g, 3+2^g, 3+3^g])));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2shift)));
shifted := [t1, t2shift];
offsets := [0, 3];

t0 := Runtime();
holt_fpf := HoltCleanFPFSubgroupClasses(P, shifted, offsets);
t_holt := Runtime() - t0;
Print("Holt clean FPF: ", Length(holt_fpf), " classes (", t_holt, "ms)\\n");

FPF_SUBDIRECT_CACHE := rec();
t0 := Runtime();
legacy_fpf := FindFPFClassesByLifting(P, shifted, offsets);
t_legacy := Runtime() - t0;
Print("Legacy FPF:     ", Length(legacy_fpf), " classes (", t_legacy, "ms)\\n");
Print("Match: ", Length(holt_fpf) = Length(legacy_fpf), "\\n");

# Case 2: partition [4,2] of S_6 with factors [T(4,k), T(2,1)]
Print("\\n=== [T(4,3), T(2,1)] on {{1..4}} x {{5,6}} ===\\n");
t1 := TransitiveGroup(4, 3);  # D_8 on 4 points
t2 := TransitiveGroup(2, 1);
t2shift := Group(List(GeneratorsOfGroup(t2),
                      g -> PermList([1, 2, 3, 4, 4+1^g, 4+2^g])));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2shift)));
shifted := [t1, t2shift];
offsets := [0, 4];

t0 := Runtime();
holt_fpf := HoltCleanFPFSubgroupClasses(P, shifted, offsets);
t_holt := Runtime() - t0;
Print("Holt clean FPF: ", Length(holt_fpf), " classes (", t_holt, "ms)\\n");

FPF_SUBDIRECT_CACHE := rec();
t0 := Runtime();
legacy_fpf := FindFPFClassesByLifting(P, shifted, offsets);
t_legacy := Runtime() - t0;
Print("Legacy FPF:     ", Length(legacy_fpf), " classes (", t_legacy, "ms)\\n");
Print("Match: ", Length(holt_fpf) = Length(legacy_fpf), "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_clean_fpf.g")
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

print("=== stdout (last 3K) ===")
print(proc.stdout[-3000:])
os.remove(cmd_file)

matches = proc.stdout.count("Match: true")
ok = matches == 2
print(f"\n[{'PASS' if ok else 'FAIL'}] Clean FPF pipeline ({matches}/2 matches)")
sys.exit(0 if ok else 1)
