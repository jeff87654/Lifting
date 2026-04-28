"""
run_bug_tests.py - Run diagnostic tests for cocycle/complement bugs

Tests the fixes for:
1. ComputeCocycleSpaceViaPcgs safety check (ngens <> Length(pcgs))
2. Cross-validation of Pcgs vs FP cocycle spaces
3. CocycleToComplement generator assertions
4. Diagnostic logging improvements
"""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/test_bug_diagnosis.g");
QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_bug_test.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_bug_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running bug diagnosis tests...")
print("=" * 60)

# Run GAP via Cygwin bash
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
    stdout, stderr = process.communicate(timeout=300)
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print("TIMEOUT! Output so far:")
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    sys.exit(1)

# Check for overall pass/fail
if "ALL TESTS PASSED" in stdout:
    print("\nSUCCESS: All diagnostic tests passed!")
    sys.exit(0)
elif "SOME TESTS FAILED" in stdout:
    print("\nFAILURE: Some diagnostic tests failed!")
    sys.exit(1)
else:
    print("\nWARNING: Could not determine test outcome")
    sys.exit(2)
