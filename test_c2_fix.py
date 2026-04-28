"""
Test the C2 optimization fix for the lifting method.

This script:
1. Unit tests HasSmallAbelianization() function
2. Runs regression tests S2-S10
"""

import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("===========================================\\n");
Print("Testing HasSmallAbelianization() function\\n");
Print("===========================================\\n\\n");

# Test 1: S4 should return true (r=1)
Print("S4 (expected true): ");
if HasSmallAbelianization(SymmetricGroup(4)) then
    Print("true - PASS\\n");
else
    Print("false - FAIL\\n");
fi;

# Test 2: A5 should return true (r=0, perfect group)
Print("A5 (expected true): ");
if HasSmallAbelianization(AlternatingGroup(5)) then
    Print("true - PASS\\n");
else
    Print("false - FAIL\\n");
fi;

# Test 3: V4 should return false (r=2)
Print("V4 (expected false): ");
if HasSmallAbelianization(Group((1,2)(3,4), (1,3)(2,4))) then
    Print("true - FAIL\\n");
else
    Print("false - PASS\\n");
fi;

# Test 4: D8 should return false (r=3)
Print("D8 (expected false): ");
if HasSmallAbelianization(DihedralGroup(IsPermGroup, 8)) then
    Print("true - FAIL\\n");
else
    Print("false - PASS\\n");
fi;

# Test 5: C4 should return true (r=1)
Print("C4 (expected true): ");
if HasSmallAbelianization(CyclicGroup(IsPermGroup, 4)) then
    Print("true - PASS\\n");
else
    Print("false - FAIL\\n");
fi;

# Test 6: A4 should return true (r=0)
Print("A4 (expected true): ");
if HasSmallAbelianization(AlternatingGroup(4)) then
    Print("true - PASS\\n");
else
    Print("false - FAIL\\n");
fi;

# Test 7: S3 should return true (r=1)
Print("S3 (expected true): ");
if HasSmallAbelianization(SymmetricGroup(3)) then
    Print("true - PASS\\n");
else
    Print("false - FAIL\\n");
fi;

Print("\\n");
Print("===========================================\\n");
Print("Running regression tests S2-S10\\n");
Print("===========================================\\n\\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

allPassed := true;

for n in [2..10] do
    expected := known[n];
    Print("Testing S_", n, " (expected ", expected, ")...\\n");
    computed := CountAllConjugacyClassesFast(n);
    if computed = expected then
        Print("S_", n, ": PASS\\n\\n");
    else
        Print("S_", n, ": FAIL (got ", computed, ", expected ", expected, ")\\n\\n");
        allPassed := false;
    fi;
od;

Print("\\n===========================================\\n");
if allPassed then
    Print("ALL TESTS PASSED\\n");
else
    Print("SOME TESTS FAILED\\n");
fi;
Print("===========================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_c2.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_c2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running C2 optimization fix tests...")
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

stdout, stderr = process.communicate(timeout=3600)
print(stdout)
if stderr:
    print("STDERR:", stderr)
