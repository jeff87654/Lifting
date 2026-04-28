"""Targeted test of [4,4,2] partition."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    PrintTo("C:/Users/jeffr/Downloads/Lifting/442_result.txt", "BREAK LOOP ERROR\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_result.txt", "Starting [4,4,2] test...\\n");

Print("\\n=== Testing [4,4,2] partition ===\\n");

startTime := Runtime();
result := FindFPFClassesForPartition(10, [4, 4, 2]);
elapsed := Runtime() - startTime;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_result.txt",
    "Completed!\\n",
    "FPF subdirects found: ", Length(result), "\\n",
    "Time: ", elapsed / 1000.0, "s\\n");

Print("\\nResult: ", Length(result), " FPF subdirects\\n");
Print("Time: ", elapsed / 1000.0, "s\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_targeted.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_targeted.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

result_file = r"C:\Users\jeffr\Downloads\Lifting\442_result.txt"
if os.path.exists(result_file):
    os.remove(result_file)

print("Testing [4,4,2] partition...")
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

print(f"Exit code: {process.returncode}")
print(f"Python timing: {elapsed:.1f}s")

if os.path.exists(result_file):
    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    with open(result_file, 'r') as f:
        print(f.read())
else:
    print("\nResult file not created - checking stdout...")
    # Show last part of stdout
    lines = stdout.strip().split('\\n')
    print(f"Output lines: {len(lines)}")
    print("Last 30 lines:")
    for line in stdout.strip().split('\\n')[-30:]:
        print(line)
