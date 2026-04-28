"""Test S10 with results written to file."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_result.txt", "ERROR: Break loop entered\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Running S10 Test ===\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := Runtime() - startTime;

# Write result to file
PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_result.txt",
    "S10 conjugacy classes: ", result, "\\n",
    "Expected: 1593\\n",
    "Time: ", elapsed / 1000.0, "s\\n",
    "Status: ", Cond(result = 1593, "PASSED", "FAILED"), "\\n");

Print("\\nResult written to s10_result.txt\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_file.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_file.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Delete old result file if exists
result_file = r"C:\Users\jeffr\Downloads\Lifting\s10_result.txt"
if os.path.exists(result_file):
    os.remove(result_file)

print("Testing S10 (results to file)...")
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

try:
    stdout, stderr = process.communicate(timeout=2400)
    elapsed = time.time() - start

    # Show progress from stdout (last lines)
    lines = stdout.strip().split('\n')
    print(f"GAP output lines: {len(lines)}")
    print("Last 20 lines of output:")
    for line in lines[-20:]:
        print(line)

    print(f"\nPython timing: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Exit code: {process.returncode}")

    # Read result file
    if os.path.exists(result_file):
        print("\n" + "=" * 60)
        print("RESULT FILE CONTENTS:")
        print("=" * 60)
        with open(result_file, 'r') as f:
            print(f.read())
    else:
        print("\nResult file not created - computation may have failed")

except subprocess.TimeoutExpired:
    process.kill()
    elapsed = time.time() - start
    print(f"\nTIMEOUT after {elapsed:.1f}s")
