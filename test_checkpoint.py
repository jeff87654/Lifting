"""Test S2-S10 with checkpoint support enabled to verify no regressions."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Create checkpoint directory
ckpt_dir = os.path.join(LIFTING_DIR, "checkpoints")
os.makedirs(ckpt_dir, exist_ok=True)

log_file = "C:/Users/jeffr/Downloads/Lifting/test_checkpoint.log"

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Enable checkpointing
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/checkpoints";

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;

for n in [1..10] do
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
    Print("\\nALL PASS with checkpointing\\n");
else
    Print("\\nSOME FAILED\\n");
fi;

LogTo();
QUIT;
'''

script_path = os.path.join(LIFTING_DIR, "test_checkpoint.g")
with open(script_path, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_checkpoint.g"

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Running S2-S10 with checkpoint support...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

with open(os.path.join(LIFTING_DIR, "test_checkpoint.log"), "r") as f:
    log = f.read()
# Show last 500 chars
print(log[-500:])

# Check if checkpoint files were created
ckpts = [f for f in os.listdir(ckpt_dir) if f.endswith('.g')]
print(f"\nCheckpoint files created: {len(ckpts)}")
for f in sorted(ckpts)[:10]:
    size = os.path.getsize(os.path.join(ckpt_dir, f))
    print(f"  {f} ({size} bytes)")

if stderr:
    print(f"stderr: {stderr[:500]}")
