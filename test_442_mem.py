"""Test [4,4,2] with extra memory and gap flags."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_mem.txt", "Starting...\\n");

Print("Testing [4,4,2]...\\n");

# Track memory before
AppendTo("C:/Users/jeffr/Downloads/Lifting/442_mem.txt",
    "Memory before: ", GasmanStatistics(), "\\n");

result := FindFPFClassesForPartition(10, [4, 4, 2]);;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_mem.txt",
    "Completed! Result: ", Length(result), "\\n",
    "Memory after: ", GasmanStatistics(), "\\n");
Print("RESULT: ", Length(result), "\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_mem.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_mem.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

out_file = r"C:\Users\jeffr\Downloads\Lifting\442_mem.txt"
if os.path.exists(out_file):
    os.remove(out_file)

print("Testing [4,4,2] with extra memory...")
start = time.time()

# Give GAP 2GB memory with -o flag
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=300)
elapsed = time.time() - start

print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(out_file):
    print("\nResult file:")
    with open(out_file, 'r') as f:
        print(f.read())
else:
    print("No output file")

# Check for RESULT in stdout
for line in stdout.split('\n'):
    if 'RESULT' in line or 'exceeded' in line.lower() or 'memory' in line.lower():
        print(f"stdout: {line}")
