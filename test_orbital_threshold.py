"""Quick test: verify S2-S10 correctness with raised orbital threshold."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = os.path.join(LIFTING_DIR, "test_orbital_threshold.log").replace("\\", "/")

# Use AppendTo for immediate output instead of LogTo which buffers
gap_code = f'''
LogTo("{log_file}");
Print("Testing S2-S10 with raised orbital threshold\\n");
Print("Start time: ", StringTime(Runtime()), "\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Run S2-S10
for n in [2..10] do
    t := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t) / 1000.0;
    Print("S", n, " = ", count, " (", elapsed, "s)\\n");
od;

Print("\\nExpected: S10 = 1593\\n");
Print("Done at ", StringTime(Runtime()), "\\n");
LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "test_orbital_threshold.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Launching S2-S10 test (timeout 900s)...")
start = time.time()
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=GAP_RUNTIME
)

stdout, stderr = proc.communicate(timeout=900)
elapsed = time.time() - start
print(f"Process exited in {elapsed:.0f}s with code {proc.returncode}")

# Print results from log
if os.path.exists(log_file.replace("/", "\\")):
    with open(log_file.replace("/", "\\"), "r") as f:
        for line in f:
            if line.startswith("S") or "Expected" in line or "Done" in line:
                print(line.rstrip())
else:
    print("No log file found")
    print("STDOUT:", stdout[:500] if stdout else "(empty)")
    print("STDERR:", stderr[:500] if stderr else "(empty)")
