"""
Test lifting_method_fast_v2.g TestFast function.
"""
import subprocess
import os
import sys

gap_commands = '''
Print("Loading lifting_method_fast_v2.g...\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("Done loading\\n");

Print("\\nRunning TestFast()...\\n");
TestFast();

Print("\\nTest complete.\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_fast_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_fast_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running TestFast()...")

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
    stdout, stderr = process.communicate(timeout=900)  # 15 minutes
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 15 minutes")
    sys.exit(1)

sys.exit(process.returncode)
