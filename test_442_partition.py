"""Test [4, 4, 2] partition specifically."""

import subprocess
import os
import time

gap_commands = '''
# Quit on errors
OnBreak := function()
    Print("\\n=== BREAK LOOP ENTERED ===\\n");
    PrintTo("*errout*", "Error occurred\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Testing [4, 4, 2] partition ===\\n");

startTime := Runtime();
result := FindFPFClassesForPartition(10, [4, 4, 2]);
elapsed := Runtime() - startTime;

Print("\\n=== RESULT ===\\n");
Print("Partition [4,4,2] FPF subdirects: ", Length(result), "\\n");
Print("Time: ", elapsed / 1000.0, "s\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing [4, 4, 2] partition...")
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
    stdout, stderr = process.communicate(timeout=600)
    elapsed = time.time() - start
    print(stdout)
    print(f"\nPython timing: {elapsed:.1f}s")
    print(f"Exit code: {process.returncode}")
    if stderr and "Syntax warning" not in stderr and "Unbound global" not in stderr:
        print("\nSTDERR:", stderr[-2000:])
except subprocess.TimeoutExpired:
    process.kill()
    elapsed = time.time() - start
    print(f"\nTIMEOUT after {elapsed:.1f}s")
