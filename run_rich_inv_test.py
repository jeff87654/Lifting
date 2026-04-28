import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_rich_inv_test.log"

result_file = "C:/Users/jeffr/Downloads/Lifting/gap_rich_inv_result.txt"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Force rich invariant upgrade on every combo
RICH_DEDUP_THRESHOLD := 1;

# Load precomputed S1-S11 caches
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear S12 from lift cache so it recomputes
Unbind(LIFT_CACHE.12);

# Clear FPF subdirect cache and H1 cache for fresh computation
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Run S12
Print("\\n=== S12 TEST (RICH_DEDUP_THRESHOLD=1) ===\\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(12);
elapsed := Runtime() - startTime;
Print("\\nS12 result: ", result, "\\n");
Print("S12 time: ", elapsed/1000.0, "s\\n");
if result = 10723 then
    Print("PASS\\n");
else
    Print("FAIL (expected 10723)\\n");
fi;

# Write result to a separate file (more reliable than LogTo)
PrintTo("{result_file}", "result=", result, "\\n",
        "time=", elapsed/1000.0, "\\n",
        "pass=", result = 10723, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 test with RICH_DEDUP_THRESHOLD=1...")
print(f"Log file: {log_file}")
start = time.time()

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
elapsed = time.time() - start
print(f"GAP exited in {elapsed:.1f}s")

# Read result file first (most reliable)
result_path = r"C:\Users\jeffr\Downloads\Lifting\gap_rich_inv_result.txt"
if os.path.exists(result_path):
    with open(result_path, "r") as f:
        print("=== RESULT ===")
        print(f.read())
else:
    print("No result file found!")

# Print last 20 lines of log
with open(log_file, "r") as f:
    log = f.read()
lines = log.strip().split('\n')
print("=== LOG TAIL ===")
for line in lines[-20:]:
    print(line)
