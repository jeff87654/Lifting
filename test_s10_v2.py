"""Test S10 computation with database - with better error handling."""

import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Running S10 Test with Database ===\\n");

startTime := Runtime();

# Use CALL_WITH_CATCH to catch any errors
result := CALL_WITH_CATCH(function()
    return CountAllConjugacyClassesFast(10);
end, []);

elapsed := Runtime() - startTime;

if result[1] = true then
    Print("\\n=== RESULT ===\\n");
    Print("S10 conjugacy classes: ", result[2], " (expected 1593)\\n");
    Print("Total time: ", elapsed / 1000.0, "s\\n");

    if result[2] = 1593 then
        Print("\\nTEST PASSED!\\n");
    else
        Print("\\nTEST FAILED! Expected 1593, got ", result[2], "\\n");
    fi;
else
    Print("\\n=== ERROR ===\\n");
    Print("Computation failed with error: ", result[2], "\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_v2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_v2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S10 with database (attempt 2)...")
print("=" * 60)
print("Expected: 1593 conjugacy classes")
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
    stdout, stderr = process.communicate(timeout=2400)  # 40 min timeout
    elapsed = time.time() - start
    print(stdout)
    print(f"\nPython timing: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    if stderr:
        print("\nSTDERR:", stderr[-2000:] if len(stderr) > 2000 else stderr)
except subprocess.TimeoutExpired:
    process.kill()
    elapsed = time.time() - start
    print(f"\nTIMEOUT after {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    stdout, stderr = process.communicate()
    print("\nPartial output (last 3000 chars):")
    print(stdout[-3000:] if len(stdout) > 3000 else stdout)
