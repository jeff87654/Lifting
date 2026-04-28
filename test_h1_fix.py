#!/usr/bin/env python3
"""Test script to verify the H^1 cohomology fix for S7 and S8."""

import subprocess
import os
import sys

gap_commands = '''
# Load the lifting algorithm (which loads cohomology and modules)
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Print configuration
Print("\\n=== H^1 Fix Verification Test ===\\n");
Print("USE_H1_COMPLEMENTS = ", USE_H1_COMPLEMENTS, "\\n");

# Test S7 first (quick sanity check)
Print("\\nTesting S7...\\n");
startTime := Runtime();
result_s7 := CountAllConjugacyClassesFast(7);
s7_time := Runtime() - startTime;
Print("S7: ", result_s7, " conjugacy classes (expected 96)\\n");
Print("S7 time: ", Float(s7_time/1000), " seconds\\n");
if result_s7 = 96 then
    Print("S7: PASS\\n");
else
    Print("S7: FAIL\\n");
fi;

# Test S8 (the main test case)
Print("\\nTesting S8...\\n");
startTime := Runtime();
result_s8 := CountAllConjugacyClassesFast(8);
s8_time := Runtime() - startTime;
Print("S8: ", result_s8, " conjugacy classes (expected 296)\\n");
Print("S8 time: ", Float(s8_time/1000), " seconds\\n");
if result_s8 = 296 then
    Print("S8: PASS\\n");
else
    Print("S8: FAIL - got ", result_s8, " expected 296\\n");
fi;

# Print H^1 timing stats
PrintH1TimingStats();

# Summary
Print("\\n=== Summary ===\\n");
if result_s7 = 96 and result_s8 = 296 then
    Print("All tests PASSED!\\n");
else
    Print("Some tests FAILED!\\n");
fi;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_h1_fix.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_h1_fix.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running H^1 fix verification test...")
print("=" * 50)

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
    stdout, stderr = process.communicate(timeout=1800)  # 30 minute timeout
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out after 30 minutes")
    sys.exit(1)
