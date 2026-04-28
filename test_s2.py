"""
Test S2 only.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing S2...\\n");
count := CountAllConjugacyClassesFast(2);
Print("S2 conjugacy classes: ", count, "\\n");

expected := 2;
if count = expected then
    Print("PASS\\n");
else
    Print("FAIL: expected ", expected, "\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s2_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s2_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S2...")

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
    stdout, stderr = process.communicate(timeout=60)
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out")
    sys.exit(1)

sys.exit(process.returncode)
