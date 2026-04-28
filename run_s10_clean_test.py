"""
run_s10_clean_test.py - Test S10 with ALL caches cleared.
Clears both H^1 cache and FPF subdirect cache to force full recomputation.
"""

import subprocess
import os
import sys
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
CROSS_VALIDATE_COCYCLES := false;

# Clear ALL caches for a clean test
ClearH1Cache();
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();

Print("\\n=== S10 CLEAN Test (All Caches Cleared) ===\\n\\n");

result := CountAllConjugacyClassesFast(10);

Print("\\nFinal S10 result: ", result, " (expected 1593)\\n");
if result = 1593 then
    Print("CORRECT\\n");
else
    Print("INCORRECT!\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_clean.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_clean.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S10 with ALL caches cleared...")
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
    stdout, stderr = process.communicate(timeout=3600)
    elapsed = time.time() - start_time

    with open(r"C:\Users\jeffr\Downloads\Lifting\s10_clean_test_output.txt", "w") as f:
        f.write(stdout)
        if stderr:
            f.write("\n\n=== STDERR ===\n")
            f.write(stderr)

    fallback_count = stdout.count("invalid complements, falling back")
    mismatch_count = stdout.count("WARNING: Cocycle space dimension mismatch")

    print(f"Completed in {elapsed:.1f} seconds ({elapsed/60:.1f} min)")
    print(f"Exit code: {process.returncode}")
    print(f"Fallback count: {fallback_count}")
    print(f"Cocycle mismatch count: {mismatch_count}")

    if stderr:
        # Show last 20 lines of stderr
        stderr_lines = stderr.strip().split('\n')
        print(f"\nSTDERR (last 20 lines):")
        for line in stderr_lines[-20:]:
            print(f"  {line}")

    if "CORRECT" in stdout:
        print("\nS10 count: CORRECT (1593)")
    elif "INCORRECT" in stdout:
        print("\nS10 count: INCORRECT!")
    else:
        print("\nS10 count: could not determine from output")

    lines = stdout.strip().split('\n')
    print(f"\nLast 50 lines of stdout:")
    for line in lines[-50:]:
        print(line)

except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print(f"TIMEOUT after {(time.time()-start_time)/60:.1f} minutes!")
    with open(r"C:\Users\jeffr\Downloads\Lifting\s10_clean_test_output.txt", "w") as f:
        f.write(stdout)
    print(stdout[-3000:] if stdout else "No output")
    sys.exit(1)
