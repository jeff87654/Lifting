"""
Test S10 - expected count is 1593.
"""
import subprocess
import os
import sys
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing S10...\\n");
Print("Expected: 1593 conjugacy classes\\n\\n");

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

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S10 (expected: 1593 classes, target: <5 minutes)...")
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
    stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout
    elapsed = time.time() - start
    print(stdout)
    print(f"\nPython measured time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    if stderr and "Error" in stderr:
        print("STDERR:", stderr[:1000])
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 10 minutes")
    sys.exit(1)

sys.exit(process.returncode)
