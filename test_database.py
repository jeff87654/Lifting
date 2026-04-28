"""
test_database.py - Test the precomputed database loading

This script verifies that:
1. The database files load correctly
2. S8 computation still gives correct result (296 classes)
"""

import subprocess
import os
import sys
import time

def test_database():
    """Test database loading and S8 computation."""

    gap_commands = '''
# Test database loading and S8 computation
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n");
Print("Testing S8 with database...\\n");
Print("===========================\\n\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(8);

Print("\\n");
Print("S8 result: ", result, "\\n");
Print("Expected:  296\\n");
if result = 296 then
    Print("STATUS: PASS\\n");
else
    Print("STATUS: FAIL\\n");
fi;
Print("Time: ", (Runtime() - startTime) / 1000.0, "s\\n");

# Print database stats
if IsBound(PrintDatabaseStats) then
    PrintDatabaseStats();
fi;

QUIT;
'''

    # Write commands to temp file
    with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test.g", "w") as f:
        f.write(gap_commands)

    # GAP environment setup
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print("Testing database loading and S8 computation...")
    print("=" * 60)

    start = time.time()

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

    stdout, stderr = process.communicate(timeout=600)

    elapsed = time.time() - start

    print(stdout)
    if stderr:
        print("STDERR:", stderr)

    print("=" * 60)
    print(f"Total elapsed time: {elapsed:.1f}s")
    print("Done!")

    # Cleanup
    try:
        os.remove(r"C:\Users\jeffr\Downloads\Lifting\temp_test.g")
    except:
        pass

if __name__ == "__main__":
    test_database()
