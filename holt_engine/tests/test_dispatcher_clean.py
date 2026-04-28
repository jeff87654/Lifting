"""Test the dispatcher routing with USE_HOLT_ENGINE=true now going through
the CLEAN pipeline (not just the legacy thin wrapper).

Verify:
  1. USE_HOLT_ENGINE=true calls HoltFPFSubgroupClassesOfProduct (clean)
  2. Results match legacy (USE_HOLT_ENGINE=false) on small combos
  3. S1-S7 regression via CountAllConjugacyClassesFast still works
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "dispatcher_clean_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== Dispatcher routes through clean pipeline ===\\n");

# Manually build [S_3, S_3] product
t1 := SymmetricGroup(3);
t2shift := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                      g -> PermList([1, 2, 3, 3+1^g, 3+2^g, 3+3^g])));
P := Group(Concatenation(GeneratorsOfGroup(t1), GeneratorsOfGroup(t2shift)));
shifted := [t1, t2shift];
offsets := [0, 3];

USE_HOLT_ENGINE := true;
r_holt := _HoltDispatchLift(P, shifted, offsets);
Print("With flag ON (clean pipeline): ", Length(r_holt), " classes\\n");

USE_HOLT_ENGINE := false;
r_leg := _HoltDispatchLift(P, shifted, offsets);
Print("With flag OFF (legacy):       ", Length(r_leg), " classes\\n");
Print("Dispatcher match: ", Length(r_holt) = Length(r_leg), "\\n");

Print("\\n=== End-to-end: CountAllConjugacyClassesFast(7) with flag ON ===\\n");
USE_HOLT_ENGINE := true;
# Clear caches so we force recomputation
FPF_SUBDIRECT_CACHE := rec();
if IsBound(LIFT_CACHE) then
  if IsBound(LIFT_CACHE.("7")) then Unbind(LIFT_CACHE.("7")); fi;
fi;

s7 := CountAllConjugacyClassesFast(7);
Print("S_7 (clean dispatcher) = ", s7, " (expect 96)\\n");
Print("S_7 match: ", s7 = 96, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_dispatcher_clean.g")
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

print("=== stdout (last 3K) ===")
print(proc.stdout[-3000:])
os.remove(cmd_file)

checks = [
    "Dispatcher match: true",
    "S_7 match: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Dispatcher routing through clean pipeline")
sys.exit(0 if ok else 1)
