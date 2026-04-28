###############################################################################
# run_partition_bench.py - Benchmark a specific partition
###############################################################################

import subprocess
import os
import time
import sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

# Partition to test: [5,4,4] of S13 (425s baseline, good candidate)
# Or [8,3,2] (198s baseline)
partition = sys.argv[1] if len(sys.argv) > 1 else "[8,3,2]"
degree = sys.argv[2] if len(sys.argv) > 2 else "13"

log_file = "C:/Users/jeffr/Downloads/Lifting/partition_bench.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S12 from cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear H^1 and FPF caches for this partition
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

t := Runtime();
result := FindFPFClassesForPartition({degree}, {partition});
elapsed := (Runtime() - t) / 1000.0;

Print("Partition {partition}: ", Length(result), " classes in ", elapsed, "s\\n");

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "partition_bench.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/partition_bench.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Running partition {partition} of S_{degree}...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=3600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

log_path = os.path.join(LIFTING_DIR, "partition_bench.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    for line in log.split("\n"):
        if "Partition" in line or "LiftThrough" in line or "parents" in line or "combo:" in line:
            print(line)
else:
    print("No log file produced")
    if stderr:
        print(f"stderr: {stderr[:500]}")
