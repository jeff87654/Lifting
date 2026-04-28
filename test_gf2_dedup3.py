"""Quick test: GF(2) orbit dedup with integer hash on S12."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_test_gf2_3.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== S12 partition [4,4,2,2] (triggers GF(2) dedup) ===\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(12, [4,4,2,2]);
Print("Result: ", Length(result), " classes (", Runtime()-t0, "ms)\\n");

Print("\\n=== Verify full S12 ===\\n");
t0 := Runtime();
count12 := CountAllConjugacyClassesFast(12);
Print("S12 = ", count12, " (", Runtime()-t0, "ms)\\n");
if count12 = 10723 then Print("PASS\\n"); else Print("FAIL!\\n"); fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_gf2_3.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_gf2_3.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=1200)
    print(f"Finished at {time.strftime('%H:%M:%S')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT")

try:
    with open(log_file, "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(k in line for k in ['GF(', 'orbit', 'SmallGroup', 'Result', 'S12', 'PASS', 'FAIL', 'RREF', 'BFS']):
            print(line)
except:
    print("Could not read log")
