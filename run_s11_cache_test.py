"""
run_s11_cache_test.py - Test S11 enumeration after H^1 cache fingerprint fix.
"""

import subprocess
import os
import sys
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
CROSS_VALIDATE_COCYCLES := false;
ClearH1Cache();

Print("\\n=== S11 Enumeration Test (Cache Fingerprint Fix) ===\\n\\n");

result := CountAllConjugacyClassesFast(11);

Print("\\nFinal S11 result: ", result, " (expected 4806)\\n");
if result = 4806 then
    Print("CORRECT\\n");
else
    Print("INCORRECT!\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s11_cache.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s11_cache.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S11 enumeration with H^1 cache fix...")
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
    stdout, stderr = process.communicate(timeout=7200)
    elapsed = time.time() - start_time

    with open(r"C:\Users\jeffr\Downloads\Lifting\s11_cache_test_output.txt", "w") as f:
        f.write(stdout)

    fallback_count = stdout.count("invalid complements, falling back")
    mismatch_count = stdout.count("WARNING: Cocycle space dimension mismatch")

    print(f"Completed in {elapsed:.1f} seconds ({elapsed/60:.1f} min)")
    print(f"Fallback count: {fallback_count}")
    print(f"Cocycle mismatch count: {mismatch_count}")

    if "CORRECT" in stdout:
        print("S11 count: CORRECT (4806)")
    elif "INCORRECT" in stdout:
        print("S11 count: INCORRECT!")
    else:
        print("S11 count: could not determine")

    lines = stdout.strip().split('\n')
    print(f"\nLast 50 lines of output:")
    for line in lines[-50:]:
        print(line)

except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print("TIMEOUT after 2 hours!")
    with open(r"C:\Users\jeffr\Downloads\Lifting\s11_cache_test_output.txt", "w") as f:
        f.write(stdout)
    print(stdout[-3000:] if stdout else "No output")
    sys.exit(1)
