"""
run_s11_cache_test2.py - Test S11 enumeration, capturing stderr and using
stdout flushing via LogTo.
"""

import subprocess
import os
import sys
import time

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/s11_cache_test_log.txt");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
CROSS_VALIDATE_COCYCLES := false;
ClearH1Cache();

Print("\\n=== S11 Enumeration Test (Cache Fingerprint Fix) ===\\n\\n");

result := CountAllConjugacyClassesFast(11);

Print("\\nFinal S11 result: ", result, " (expected 4806)\\n");
if result = 4806 then
    Print("S11 CORRECT\\n");
else
    Print("S11 INCORRECT!\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s11_cache2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s11_cache2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S11 enumeration with H^1 cache fix (v2, with LogTo)...")
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

    print(f"Completed in {elapsed:.1f} seconds ({elapsed/60:.1f} min)")
    print(f"Exit code: {process.returncode}")

    if stderr:
        # Filter out syntax warnings
        real_errors = [l for l in stderr.split('\n')
                      if l.strip() and 'Syntax warning' not in l and '^' not in l.strip()]
        if real_errors:
            print(f"STDERR (non-warning): {len(real_errors)} lines")
            for line in real_errors[:20]:
                print(f"  {line}")

    # Check the LogTo output
    try:
        with open(r"C:\Users\jeffr\Downloads\Lifting\s11_cache_test_log.txt", "r") as f:
            log = f.read()

        fallback_count = log.count("invalid complements, falling back")
        print(f"Fallback count: {fallback_count}")

        if "S11 CORRECT" in log:
            print("S11 count: CORRECT (4806)")
        elif "S11 INCORRECT" in log:
            print("S11 count: INCORRECT!")
        elif "Total S_11:" in log:
            # Extract the total
            for line in log.split('\n'):
                if "Total S_11:" in line:
                    print(f"  {line.strip()}")
        else:
            print("S11: did not complete")
            # Show last 30 lines of log
            lines = log.strip().split('\n')
            print(f"\nLast 30 lines of log:")
            for line in lines[-30:]:
                print(line)
    except FileNotFoundError:
        print("LogTo file not created!")
        # Fall back to stdout
        lines = stdout.strip().split('\n')
        print(f"\nLast 30 lines of stdout:")
        for line in lines[-30:]:
            print(line)

except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print("TIMEOUT after 2 hours!")
    sys.exit(1)
