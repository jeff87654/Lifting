"""
Test script to verify S8 works correctly with USE_H1_COMPLEMENTS disabled.
"""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Disable H^1 complement method entirely
USE_H1_COMPLEMENTS := false;

# Run S8 test
Print("\\n=== Testing S8 with USE_H1_COMPLEMENTS = false ===\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
endTime := Runtime();

Print("\\nS8 result: ", result, " conjugacy classes\\n");
Print("Time: ", Float(endTime - startTime)/1000.0, " seconds\\n");

if result = 296 then
    Print("\\n*** TEST PASSED: S8 returns 296 (correct) ***\\n");
else
    Print("\\n*** TEST FAILED: S8 returns ", result, " (expected 296) ***\\n");
fi;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_h1_disabled_test.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_h1_disabled_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S8 test with USE_H1_COMPLEMENTS = false...")
print("=" * 60)

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
    stdout, stderr = process.communicate(timeout=600)
    print(stdout)
    if stderr:
        print("STDERR:", stderr)

    if "TEST PASSED" in stdout:
        print("\n" + "=" * 60)
        print("Confirmed: USE_H1_COMPLEMENTS=false produces correct results")
        sys.exit(0)
    elif "TEST FAILED" in stdout:
        print("\n" + "=" * 60)
        print("Even with H^1 disabled, wrong result!")
        sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("Test result unclear")
        sys.exit(2)

except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(3)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(4)
