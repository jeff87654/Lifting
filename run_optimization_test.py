import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Correctness: S2-S8
Print("\\n=== CORRECTNESS TEST ===\\n");
TestFast();

# Performance: S11 (includes S2-S10 recursively)
Print("\\n=== OPT A + LOCAL DEDUP: S11 ===\\n");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
CountAllConjugacyClassesFast(11);

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

print("TEST: Optimization A + local byInvariant (independent per-combination dedup)")
start = time.time()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)
elapsed = time.time() - start
print(f"GAP finished in {elapsed:.1f}s")

if stderr.strip():
    print(f"[stderr] {stderr[:1000]}")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output.log", "r") as f:
        log = f.read()

    # Check correctness
    for line in log.split('\n'):
        if 'FAIL' in line or 'PASS' in line or 'All tests' in line:
            print(line.strip())

    # S11 results
    for line in log.split('\n'):
        if 'Total S_11' in line:
            print(line.strip())

    print("\n--- S11 partition details ---")
    in_s11 = False
    for line in log.split('\n'):
        if 'Processing 14 partitions' in line:
            in_s11 = True
        if in_s11:
            if 'Partition' in line or 'Time:' in line or 'Final count' in line or 'Total S_11' in line:
                print(line.strip())
            if 'Total S_11' in line:
                break
except FileNotFoundError:
    print("Log file not found!")
    print(f"STDOUT: {stdout[:3000]}")
