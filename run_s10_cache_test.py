"""
run_s10_cache_test.py - Test S10 enumeration after H^1 cache fingerprint fix.
Checks for "invalid complements, falling back" messages.
"""

import subprocess
import os
import sys
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
CROSS_VALIDATE_COCYCLES := false;
ClearH1Cache();

Print("\\n=== S10 Enumeration Test (Cache Fingerprint Fix) ===\\n\\n");

result := CountAllConjugacyClassesFast(10);

Print("\\nFinal S10 result: ", result, " (expected 1593)\\n");
if result = 1593 then
    Print("CORRECT\\n");
else
    Print("INCORRECT!\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_cache.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_cache.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S10 enumeration with H^1 cache fix...")
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

start_time = time.time()
try:
    stdout, stderr = process.communicate(timeout=1800)
    elapsed = time.time() - start_time

    # Save full output
    with open(r"C:\Users\jeffr\Downloads\Lifting\s10_cache_test_output.txt", "w") as f:
        f.write(stdout)

    # Count fallback messages
    fallback_count = stdout.count("invalid complements, falling back")
    mismatch_count = stdout.count("WARNING: Cocycle space dimension mismatch")

    print(f"Completed in {elapsed:.1f} seconds")
    print(f"Fallback count: {fallback_count}")
    print(f"Cocycle mismatch count: {mismatch_count}")

    if "CORRECT" in stdout:
        print("S10 count: CORRECT (1593)")
    elif "INCORRECT" in stdout:
        print("S10 count: INCORRECT!")
    else:
        print("S10 count: could not determine")

    # Print last 40 lines
    lines = stdout.strip().split('\n')
    print(f"\nLast 40 lines of output:")
    for line in lines[-40:]:
        print(line)

except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print("TIMEOUT after 30 minutes!")
    print(stdout[-3000:] if stdout else "No output")
    sys.exit(1)
