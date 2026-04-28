"""Test S2-S10 with TF-database disabled — isolates whether M3 caused a new failure."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "test_m3_disabled.log"

gap_commands = f'''
USE_TF_DATABASE := false;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
for n in [2..10] do
    Print("\\nTesting S_", n, " (expected: ", known[n], ")\\n");
    result := CountAllConjugacyClassesFast(n);
    Print("S_", n, " = ", result, " ",
          function() if result = known[n] then return "PASS"; else return "FAIL"; fi; end(), "\\n");
od;
Print("\\nDONE (USE_TF_DATABASE disabled)\\n");
LogTo();
QUIT;
'''

TMP = LIFTING / "temp_m3_disabled.g"
TMP.write_text(gap_commands)

if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_m3_disabled.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=600)

print("=== STDOUT (tail) ===")
print(stdout[-3000:])
print("\n=== STDERR (tail) ===")
print(stderr[-1500:])
