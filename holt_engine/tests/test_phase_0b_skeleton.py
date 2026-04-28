"""Phase 0b smoke test: load the holt_engine skeleton and run RegressionCheck.

Success criteria (from plan):
  - Read("holt_engine/loader.g") succeeds (no GAP errors)
  - RegressionCheck(5) returns true via LIFT_CACHE
"""

import os
import subprocess
import sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_0b_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Print("LIFT_CACHE bound: ", IsBound(LIFT_CACHE), "\\n");
Print("LIFT_CACHE.5 = ", LIFT_CACHE.("5"), "\\n");
Print("OEIS S5 expected 19, got: ", HOLT_OEIS_COUNTS.("5"), "\\n");
Print("HoltRegressionCheck(5) = ", HoltRegressionCheck(5), "\\n");
Print("HoltRegressionCheck(10) = ", HoltRegressionCheck(10), "\\n");
Print("HoltRegressionCheck(17) = ", HoltRegressionCheck(17), "\\n");
Print("HoltCountConjugacyClasses(5) = ", HoltCountConjugacyClasses(5), "\\n");
Print("HOLT_ENGINE_LOADED = ", HOLT_ENGINE_LOADED, "\\n");
Print("USE_HOLT_ENGINE = ", USE_HOLT_ENGINE, "\\n");
LogTo();
QUIT;
'''

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_0b.g")
with open(cmd_file, "w") as f:
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
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    timeout=300,
)

print("=== stdout ===")
print(proc.stdout)
print("=== stderr ===")
print(proc.stderr[-2000:] if proc.stderr else "(empty)")

if os.path.exists(LOG_FILE):
    print("=== GAP log ===")
    with open(LOG_FILE) as f:
        print(f.read())

os.remove(cmd_file)

# Exit status based on whether RegressionCheck(5) = true appeared
ok = proc.stdout and "HoltRegressionCheck(5) = true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 0b smoke test")
sys.exit(0 if ok else 1)
