"""
Run S2-S10 verification after optimization changes.
Tests that all computed values match OEIS A000638.
Uses AppendTo for reliable flushed output after each test.
"""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_verify_output.log"

gap_commands = f'''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for fresh computation
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPassed := true;
startTime := Runtime();

PrintTo("{log_file}", "Verification test after optimizations\\n");
AppendTo("{log_file}", "========================================\\n\\n");

for n in [2..10] do
    expected := known[n];
    t0 := Runtime();
    computed := CountAllConjugacyClassesFast(n);
    elapsed := Runtime() - t0;
    if computed = expected then
        AppendTo("{log_file}", "S_", n, ": PASS (", computed, ") in ", elapsed/1000.0, "s\\n");
    else
        AppendTo("{log_file}", "S_", n, ": FAIL (got ", computed, ", expected ", expected, ") in ", elapsed/1000.0, "s\\n");
        allPassed := false;
    fi;
od;

totalTime := Runtime() - startTime;
AppendTo("{log_file}", "\\n========================================\\n");
AppendTo("{log_file}", "Total time: ", totalTime / 1000.0, "s\\n");
if allPassed then
    AppendTo("{log_file}", "ALL TESTS PASSED\\n");
else
    AppendTo("{log_file}", "SOME TESTS FAILED\\n");
fi;
AppendTo("{log_file}", "========================================\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Clear old log
try:
    os.remove(r"C:\Users\jeffr\Downloads\Lifting\gap_verify_output.log")
except:
    pass

print(f"Starting GAP verification test at {time.strftime('%H:%M:%S')}")
print(f"Log file: {log_file}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=3600)
    print(f"GAP process finished at {time.strftime('%H:%M:%S')}")
    if stderr and "error" in stderr.lower():
        print(f"STDERR (errors): {stderr[:1000]}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 60 minutes")

# Read log
try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_verify_output.log", "r") as f:
        log = f.read()
    print("\n=== GAP LOG OUTPUT ===")
    print(log)
except FileNotFoundError:
    print("Log file not found")
