import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_s11_s12_clean_output.txt"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# CLEAR stale cache from database (was computed with old buggy code)
FPF_SUBDIRECT_CACHE := rec();

Print("\\n=== S11-S12 Clean Test (cache cleared) ===\\n\\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593, 3094, 10723];

for n in [11, 12] do
    Print("\\n========================================\\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\\n");
    Print("========================================\\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\\nS_", n, " Result: ", result, "\\n");
    Print("Expected: ", known[n], "\\n");
    if result = known[n] then
        Print("Status: PASS\\n");
    else
        Print("Status: FAIL (off by ", known[n] - result, ")\\n");
    fi;
    Print("Time: ", elapsed, " seconds\\n");
od;

Print("\\n========================================\\n");
Print("Test Complete\\n");
Print("========================================\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_s11_s12_clean_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s11_s12_clean_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

start = time.time()
print("Launching S11-S12 clean test (cache cleared)...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)
wall = time.time() - start

print(f"Wall clock: {wall:.1f}s")
for line in stdout.split('\n'):
    if any(kw in line for kw in ['Result', 'Expected', 'PASS', 'FAIL', 'Status', 'Time:', 'Total', 'Complete']):
        print(line)
