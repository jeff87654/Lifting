"""Test [4,4,2] with error catching."""

import subprocess
import os
import time

gap_commands = '''
# Catch ALL errors
OnBreak := function()
    AppendTo("C:/Users/jeffr/Downloads/Lifting/442_error.txt",
        "BREAK LOOP entered!\\n",
        "Error: ", CURRENT_ERROR_MESSAGE, "\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_error.txt", "Starting [4,4,2]...\\n");

Print("Testing [4,4,2]...\\n");
result := FindFPFClassesForPartition(10, [4, 4, 2]);;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_error.txt",
    "Completed! Result: ", Length(result), "\\n");
Print("RESULT: ", Length(result), " classes\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_catch.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_catch.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

error_file = r"C:\Users\jeffr\Downloads\Lifting\442_error.txt"
if os.path.exists(error_file):
    os.remove(error_file)

print("Testing [4,4,2] with error catching...")
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

stdout, stderr = process.communicate(timeout=300)
elapsed = time.time() - start

print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(error_file):
    print("\nError/Result file:")
    with open(error_file, 'r') as f:
        print(f.read())
else:
    print("\nNo error file created")

# Check stderr for errors
stderr_lines = [l for l in stderr.split('\\n')
                if l.strip() and 'Syntax warning' not in l and 'Unbound global' not in l]
if stderr_lines:
    print("\nFiltered STDERR:")
    for line in stderr_lines[:20]:
        print(line)
