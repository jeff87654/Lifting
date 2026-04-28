"""Test the two S15 partitions affected by the orbital bug: [5,4,4,2] and [6,6,3].
Expected: [5,4,4,2]=4753, [6,6,3]=3248 with orbital ON."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/s15_partitions_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := true;

# ========== TEST 1: [5,4,4,2] ==========
Print("\\n========== Partition [5,4,4,2] ==========\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
result1 := FindFPFClassesForPartition(15, [5,4,4,2]);
t1 := Runtime() - t0;
Print("  [5,4,4,2]: ", Length(result1), " (expected 4753) ", t1, "ms\\n");
if Length(result1) = 4753 then
    Print("  [5,4,4,2] PASSED\\n");
else
    Print("  [5,4,4,2] FAILED (delta = ", 4753 - Length(result1), ")\\n");
fi;

# ========== TEST 2: [6,6,3] ==========
Print("\\n========== Partition [6,6,3] ==========\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
result2 := FindFPFClassesForPartition(15, [6,6,3]);
t2 := Runtime() - t0;
Print("  [6,6,3]: ", Length(result2), " (expected 3248) ", t2, "ms\\n");
if Length(result2) = 3248 then
    Print("  [6,6,3] PASSED\\n");
else
    Print("  [6,6,3] FAILED (delta = ", 3248 - Length(result2), ")\\n");
fi;

# ========== SUMMARY ==========
Print("\\n========== SUMMARY ==========\\n");
Print("[5,4,4,2] = ", Length(result1), " (expected 4753)\\n");
Print("[6,6,3] = ", Length(result2), " (expected 3248)\\n");
if Length(result1) = 4753 and Length(result2) = 3248 then
    Print("BOTH PASSED - Orbital fix verified for S15!\\n");
else
    Print("SOME TESTS FAILED\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_s15_partitions_test.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s15_partitions_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S15 partition tests at {time.strftime('%H:%M:%S')}")
print("Testing [5,4,4,2] (expected 4753) and [6,6,3] (expected 3248) with orbital ON")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(x in line for x in ['==========', 'PASS', 'FAIL', 'expected', 'delta', 'BOTH', 'SOME']):
            print(line.strip())
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
