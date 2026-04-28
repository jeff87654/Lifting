"""Test [4, 4, 2] partition with explicit flushing."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    Print("\\n=== BREAK LOOP ENTERED ===\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Testing [4, 4, 2] partition ===\\n");

startTime := Runtime();;
result := FindFPFClassesForPartition(10, [4, 4, 2]);;
elapsed := Runtime() - startTime;;

Print("\\n");;
Print("=== RESULT ===\\n");;
Print("Partition [4,4,2] FPF subdirects: ", Length(result), "\\n");;
Print("Time: ", elapsed / 1000.0, "s\\n");;
Print("=== DONE ===\\n");;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_v2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_v2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing [4, 4, 2] partition (v2)...")
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

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start

# Print last part of output
lines = stdout.split('\n')
if len(lines) > 30:
    print("... (output truncated) ...")
    print('\n'.join(lines[-30:]))
else:
    print(stdout)

print(f"\nPython timing: {elapsed:.1f}s")
print(f"Exit code: {process.returncode}")
