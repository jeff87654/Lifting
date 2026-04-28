"""Simple test writing result immediately."""

import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing [4,4,2]...\\n");
result := FindFPFClassesForPartition(10, [4, 4, 2]);;
Print("RESULT: ", Length(result), " classes\\n");
PrintTo("C:/Users/jeffr/Downloads/Lifting/442_out.txt", Length(result));
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_simple.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_simple.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

out_file = r"C:\Users\jeffr\Downloads\Lifting\442_out.txt"
if os.path.exists(out_file):
    os.remove(out_file)

print("Testing [4,4,2]...")
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

# Check output file
if os.path.exists(out_file):
    with open(out_file, 'r') as f:
        print(f"Result from file: {f.read().strip()} classes")
else:
    print("No output file created")

# Check stdout for RESULT line
for line in stdout.split('\\n'):
    if 'RESULT' in line:
        print(f"From stdout: {line}")
