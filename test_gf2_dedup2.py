"""Test GF(2) orbit dedup on S12 partition [2,2,2,2,2,2] (C_2^6 case)."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_test_gf2_dedup2.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
# Load precomputed S1-S11 counts
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Test 1: S12 partition [2,2,2,2,2,2] with GF(2) dedup ===\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(12, [2,2,2,2,2,2]);
Print("Result: ", Length(result), " classes (", Runtime()-t0, "ms)\\n");

Print("\\n=== Test 2: S10 partition [2,2,2,2,2] (smaller, for reference) ===\\n");
t0 := Runtime();
result2 := FindFPFClassesForPartition(10, [2,2,2,2,2]);
Print("Result: ", Length(result2), " classes (", Runtime()-t0, "ms)\\n");

Print("\\n=== Test 3: S12 partition [4,4,2,2] (mixed V4 + C2 case) ===\\n");
t0 := Runtime();
result3 := FindFPFClassesForPartition(12, [4,4,2,2]);
Print("Result: ", Length(result3), " classes (", Runtime()-t0, "ms)\\n");

Print("\\n=== Test 4: Full S12 (verify 10723) ===\\n");
t0 := Runtime();
count12 := CountAllConjugacyClassesFast(12);
Print("S12 = ", count12, " (", Runtime()-t0, "ms)\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_gf2_2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_gf2_2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=1200)
    print(f"GAP finished at {time.strftime('%H:%M:%S')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 1200s")

# Read log
try:
    with open(log_file, "r") as f:
        log = f.read()
    # Show key parts
    lines = log.split('\n')
    for line in lines:
        if any(k in line for k in ['Test', 'Result', 'SmallGroup', 'GF(2)', 'GF(', 'orbit', 'S12', 'combo:', 'Total']):
            print(line)
except:
    print("Could not read log file")
