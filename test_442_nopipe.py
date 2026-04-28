"""Test [4,4,2] with output redirected to file (no pipe buffering)."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

# Redirect all GAP output to file
SetPrintFormattingStatus("*stdout*", false);

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_nopipe.txt", "Starting...\\n");

result := FindFPFClassesForPartition(10, [4, 4, 2]);;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_nopipe.txt",
    "DONE! Classes: ", Length(result), "\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_nopipe.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_nopipe.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

out_file = r"C:\Users\jeffr\Downloads\Lifting\442_nopipe.txt"
if os.path.exists(out_file):
    os.remove(out_file)

print("Testing [4,4,2] with file redirect...")
start = time.time()

# Redirect stdout/stderr to files to avoid pipe buffer issues
with open(r"C:\Users\jeffr\Downloads\Lifting\442_stdout.txt", "w") as stdout_f, \
     open(r"C:\Users\jeffr\Downloads\Lifting\442_stderr.txt", "w") as stderr_f:

    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=stdout_f,
        stderr=stderr_f,
        text=True,
        env=env,
        cwd=gap_runtime
    )

    process.wait(timeout=600)

elapsed = time.time() - start
print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(out_file):
    print("\nResult file:")
    with open(out_file, 'r') as f:
        print(f.read())
else:
    print("No result file")

# Check stdout file
stdout_file = r"C:\Users\jeffr\Downloads\Lifting\442_stdout.txt"
if os.path.exists(stdout_file):
    with open(stdout_file, 'r') as f:
        content = f.read()
        lines = content.strip().split('\n')
        print(f"\nStdout file: {len(lines)} lines")
        print("Last 10 lines:")
        for line in lines[-10:]:
            print(f"  {line}")
