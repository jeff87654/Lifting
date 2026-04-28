"""
Simple test to check if GAP can load the files.
"""
import subprocess
import os
import sys

gap_commands = '''
Print("Loading lifting_algorithm.g...\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Print("Done loading lifting_algorithm.g\\n");

Print("Testing S3 x S3...\\n");
TestLiftingS3xS3();

Print("Test complete.\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_simple_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_simple_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running simple test...")

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
    stdout, stderr = process.communicate(timeout=120)
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out")
    sys.exit(1)

sys.exit(process.returncode)
