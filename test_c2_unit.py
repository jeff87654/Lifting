"""
Unit test for HasSmallAbelianization() function only.
"""

import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("===========================================\\n");
Print("Testing HasSmallAbelianization() function\\n");
Print("===========================================\\n\\n");

passed := 0;
failed := 0;

# Test 1: S4 should return true (r=1)
Print("Test 1: S4 (expected true): ");
if HasSmallAbelianization(SymmetricGroup(4)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 2: A5 should return true (r=0, perfect group)
Print("Test 2: A5 (expected true): ");
if HasSmallAbelianization(AlternatingGroup(5)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 3: V4 should return false (r=2)
Print("Test 3: V4 (expected false): ");
if HasSmallAbelianization(Group((1,2)(3,4), (1,3)(2,4))) then
    Print("true - FAIL\\n");
    failed := failed + 1;
else
    Print("false - PASS\\n");
    passed := passed + 1;
fi;

# Test 4: D8 should return false (r=3)
Print("Test 4: D8 (expected false): ");
if HasSmallAbelianization(DihedralGroup(IsPermGroup, 8)) then
    Print("true - FAIL\\n");
    failed := failed + 1;
else
    Print("false - PASS\\n");
    passed := passed + 1;
fi;

# Test 5: C4 should return true (r=1)
Print("Test 5: C4 (expected true): ");
if HasSmallAbelianization(CyclicGroup(IsPermGroup, 4)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 6: A4 should return true (r=0)
Print("Test 6: A4 (expected true): ");
if HasSmallAbelianization(AlternatingGroup(4)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 7: S3 should return true (r=1)
Print("Test 7: S3 (expected true): ");
if HasSmallAbelianization(SymmetricGroup(3)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 8: C2 x C2 should return false (r=2)
Print("Test 8: C2xC2 (expected false): ");
if HasSmallAbelianization(Group((1,2), (3,4))) then
    Print("true - FAIL\\n");
    failed := failed + 1;
else
    Print("false - PASS\\n");
    passed := passed + 1;
fi;

# Test 9: S5 should return true (r=1)
Print("Test 9: S5 (expected true): ");
if HasSmallAbelianization(SymmetricGroup(5)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

# Test 10: C2 should return true (r=1)
Print("Test 10: C2 (expected true): ");
if HasSmallAbelianization(CyclicGroup(IsPermGroup, 2)) then
    Print("true - PASS\\n");
    passed := passed + 1;
else
    Print("false - FAIL\\n");
    failed := failed + 1;
fi;

Print("\\n===========================================\\n");
Print("Results: ", passed, " passed, ", failed, " failed\\n");
if failed = 0 then
    Print("ALL UNIT TESTS PASSED\\n");
else
    Print("SOME UNIT TESTS FAILED\\n");
fi;
Print("===========================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_unit.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_unit.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running HasSmallAbelianization() unit tests...")
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

stdout, stderr = process.communicate(timeout=120)
print(stdout)
if stderr and "Syntax warning" not in stderr:
    print("STDERR:", stderr)
