"""Test S10 computation with database."""

import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Running S10 Test with Database ===\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := Runtime() - startTime;

Print("\\n=== RESULT ===\\n");
Print("S10 conjugacy classes: ", result, " (expected 1593)\\n");
Print("Total time: ", elapsed / 1000.0, "s\\n");

if result = 1593 then
    Print("\\nTEST PASSED!\\n");
else
    Print("\\nTEST FAILED! Expected 1593, got ", result, "\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_db.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_db.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S10 with database...")
print("=" * 60)
print("Expected: 1593 conjugacy classes")
print("Previous time without full database: ~8 minutes")
print("=" * 60)

start = time.time()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=1800)  # 30 min timeout
elapsed = time.time() - start

print(stdout)
print(f"\nPython timing: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")

if stderr and "Syntax warning" not in stderr and "Unbound global" not in stderr:
    print("STDERR:", stderr)
