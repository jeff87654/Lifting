"""Test checkpoint resume: run S8 with existing checkpoint files."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

log_file = "C:/Users/jeffr/Downloads/Lifting/test_checkpoint_resume.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Enable checkpointing (existing files from previous run)
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/checkpoints";

# Clear caches but DON'T clear checkpoint files
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Run S1-S8 (S8 has interesting partitions with checkpoint files)
expected := [1, 2, 4, 11, 19, 56, 96, 296];
allPass := true;

for n in [1..8] do
    t0 := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t0) / 1000.0;
    if result = expected[n] then
        Print("S", n, " = ", result, " PASS (", elapsed, "s)\\n");
    else
        Print("S", n, " = ", result, " FAIL (expected ", expected[n], ")\\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\\nALL PASS (checkpoint resume)\\n");
else
    Print("\\nSOME FAILED\\n");
fi;

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "test_checkpoint_resume.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_checkpoint_resume.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S1-S8 with checkpoint resume...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=120)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "test_checkpoint_resume.log"), "r") as f:
    log = f.read()

# Show relevant lines
for line in log.split('\n'):
    if any(x in line for x in ['PASS', 'FAIL', 'CHECKPOINT', 'ALL']):
        print(line.strip())

if stderr and 'Syntax warning' not in stderr[:200]:
    print(f"stderr: {stderr[:500]}")
