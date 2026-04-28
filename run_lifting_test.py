"""
Run lifting algorithm tests to verify S2-S10 still work.
"""
import subprocess
import os
import sys

gap_commands = '''
# Load the lifting algorithm (which now uses cohomology)
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Run tests for S2-S8 (quick)
Print("Running TestFast() for S2-S8...\\n");
TestFast();

Print("\\n\\nTest complete.\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_lifting_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_lifting_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running lifting algorithm tests for S2-S8...")
print("=" * 60)

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
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 10 minutes")
    sys.exit(1)

sys.exit(process.returncode)
