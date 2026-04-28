###############################################################################
# run_bisect.py - Bisect the S6 overcounting bug
#
# Tests S6 with various optimizations disabled to identify the culprit.
###############################################################################

import subprocess
import os
import sys
import time
import re

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

def run_gap(gap_code, label, timeout=600):
    """Run GAP code and return the log output."""
    log_file = f"C:/Users/jeffr/Downloads/Lifting/bisect_{label}.log"
    script_file = os.path.join(LIFTING_DIR, f"bisect_{label}.g")

    full_code = f'''
LogTo("{log_file}");
Print("=== Test: {label} ===\\n");
{gap_code}
LogTo();
QUIT;
'''
    with open(script_file, "w") as f:
        f.write(full_code)

    script_cygwin = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/bisect_{label}.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
    ]

    start = time.time()
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=GAP_RUNTIME
        )
        stdout, stderr = process.communicate(timeout=timeout)
        elapsed = time.time() - start
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"  TIMEOUT after {timeout}s")
        return None

    log_path = os.path.join(LIFTING_DIR, f"bisect_{label}.log")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log = f.read()
        print(f"  Completed in {elapsed:.1f}s (rc={process.returncode})")
        return log
    else:
        print(f"  No log file produced (rc={process.returncode})")
        if stderr:
            print(f"  stderr: {stderr[:300]}")
        return None


def extract_count(log, n):
    """Extract the S_n count from log output."""
    if log is None:
        return None
    # Look for patterns like "S_6 has 56 conjugacy classes" or "Total: 56"
    # or CountAllConjugacyClassesFast output
    for pattern in [
        rf'S_{n}\s*(?:has|=|:)\s*(\d+)',
        rf'Total.*?(\d+)',
        rf'CountAllConjugacyClassesFast.*?(\d+)',
        rf'count_s{n}\s*=\s*(\d+)',
        rf'result\s*=\s*(\d+)',
    ]:
        m = re.search(pattern, log)
        if m:
            return int(m.group(1))
    return None


# Expected values
EXPECTED = {6: 56, 7: 96, 8: 296}

# Test 1: Full code as-is (should reproduce bug)
print("\n=== Test 1: Current code (should reproduce bug) ===")
log = run_gap('''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
count := CountAllConjugacyClassesFast(6);
Print("S_6 = ", count, " (", (Runtime()-t)/1000.0, "s)\\n");
if count = 56 then Print("PASS\\n"); else Print("FAIL (expected 56)\\n"); fi;
''', "test1_current")
if log:
    print(log[-500:] if len(log) > 500 else log)

# Test 2: Disable H^1 orbital (USE_H1_ORBITAL := false)
print("\n=== Test 2: Disable H^1 orbital ===")
log = run_gap('''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
count := CountAllConjugacyClassesFast(6);
Print("S_6 = ", count, " (", (Runtime()-t)/1000.0, "s)\\n");
if count = 56 then Print("PASS\\n"); else Print("FAIL (expected 56)\\n"); fi;
''', "test2_no_orbital")
if log:
    print(log[-500:] if len(log) > 500 else log)

# Test 3: Disable ALL H^1 (USE_H1_COMPLEMENTS := false)
print("\n=== Test 3: Disable ALL H^1 ===")
log = run_gap('''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
USE_H1_COMPLEMENTS := false;
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
count := CountAllConjugacyClassesFast(6);
Print("S_6 = ", count, " (", (Runtime()-t)/1000.0, "s)\\n");
if count = 56 then Print("PASS\\n"); else Print("FAIL (expected 56)\\n"); fi;
''', "test3_no_h1")
if log:
    print(log[-500:] if len(log) > 500 else log)

print("\n=== Summary ===")
print("Test 1 (current code):     See above")
print("Test 2 (no orbital):       See above")
print("Test 3 (no H^1 at all):    See above")
print("If Test 3 passes but Test 2 fails -> bug is in H^1 method (modules.g Opt 4)")
print("If Test 2 passes but Test 1 fails -> bug is in orbital method (h1_action.g Opt 5)")
print("If Test 3 also fails -> bug is in lifting infrastructure (Opt 1 profiling?)")
