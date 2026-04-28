"""Test the optimized integer BFS in _DeduplicateEAFPFbyGF2Orbits.
Run [4,4,4] for S12 which triggers BFS on C2^6, compare with reference count.
Also run [2,2,2,2,2,2] for S12 to get a pure C2^6 BFS test.
"""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/test_bfs_opt.log"

gap_code = f'''
LogTo("{log_file}");
Print("=== BFS Optimization Test ===\n");
Print("Loading code...\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Print("Code loaded at ", Runtime()/1000, "s\n");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test 1: [2,2,2,2,2,2] for S12 - pure C2^6, exercises BFS directly
Print("\n--- Test 1: S12 [2,2,2,2,2,2] ---\n");
t0 := Runtime();
r1 := FindFPFClassesForPartition(12, [2,2,2,2,2,2]);
Print("[2,2,2,2,2,2]: ", Length(r1), " classes (", Runtime()-t0, "ms)\n");

# Test 2: [4,4,4] for S12 - includes V4^3 = C2^6 combo
Print("\n--- Test 2: S12 [4,4,4] ---\n");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
r2 := FindFPFClassesForPartition(12, [4,4,4]);
Print("[4,4,4]: ", Length(r2), " classes (", Runtime()-t0, "ms)\n");

# Test 3: Full S2-S10 regression
Print("\n--- Test 3: S2-S10 regression ---\n");
# Reset LIFT_CACHE to force recomputation
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
count := CountAllConjugacyClassesFast(10);
Print("S10 = ", count, " (expected 1593) (", Runtime()-t0, "ms)\n");
if count = 1593 then
    Print("S2-S10: PASS\n");
else
    Print("S2-S10: FAIL! Got ", count, " expected 1593\n");
fi;

Print("\n=== ALL TESTS COMPLETE ===\n");
LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "temp_test_bfs_opt.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_bfs_opt.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Launching BFS optimization test at {time.strftime('%H:%M:%S')}")
proc = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 4g "{script_path}" 2>&1'],
    stdout=open(os.path.join(LIFTING_DIR, "test_bfs_opt_stdout.txt"), "w"),
    stderr=subprocess.STDOUT,
    env=env,
    cwd=gap_runtime
)
print(f"Test PID: {proc.pid}")
print("Waiting for completion...")
proc.wait(timeout=600)
print(f"Test completed with return code {proc.returncode}")

# Read log
if os.path.exists(log_file.replace("/", "\\")):
    with open(log_file.replace("/", "\\"), "r") as f:
        log = f.read()
    print("\n=== TEST LOG ===")
    print(log[-3000:] if len(log) > 3000 else log)
else:
    print("No log file found! Check stdout:")
    stdout_file = os.path.join(LIFTING_DIR, "test_bfs_opt_stdout.txt")
    with open(stdout_file, "r") as f:
        print(f.read()[-3000:])
