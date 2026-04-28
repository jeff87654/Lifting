"""
Run cohomology tests via GAP.
"""
import subprocess
import os
import sys

gap_commands = '''
# Run cohomology test suite
Read("C:/Users/jeffr/Downloads/Lifting/test_cohomology.g");
RunAllTests();
QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cohomology_test.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cohomology_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running cohomology tests...")
print("=" * 60)

# Run GAP via Cygwin bash
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
