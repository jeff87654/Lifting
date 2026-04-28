"""
Test S10 only (with S9 cached from previous run).
"""
import subprocess
import os
import sys
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing S10 (S9 should be cached)...\\n");

startTime := Runtime();
count := CountAllConjugacyClassesFast(10);
endTime := Runtime();

Print("\\n========================================\\n");
Print("S10 conjugacy classes: ", count, "\\n");
Print("Total time: ", StringTime(endTime - startTime), "\\n");

if count = 1593 then
    Print("PASS\\n");
else
    Print("FAIL: expected 1593\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_only.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_only.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S10...")
print("=" * 60)

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

try:
    stdout, stderr = process.communicate(timeout=1200)  # 20 minute timeout
    elapsed = time.time() - start
    print(stdout)
    print(f"\nPython measured time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
except subprocess.TimeoutExpired:
    process.kill()
    elapsed = time.time() - start
    print(f"Test timed out after {elapsed/60:.1f} minutes")
    sys.exit(1)

sys.exit(process.returncode)
