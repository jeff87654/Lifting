"""
Test S2-S6.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

expected := [2, 4, 11, 19, 56];

for n in [2..6] do
    Print("Testing S", n, "...\\n");
    count := CountAllConjugacyClassesFast(n);
    Print("S", n, " conjugacy classes: ", count, "\\n");
    if count = expected[n-1] then
        Print("PASS\\n\\n");
    else
        Print("FAIL: expected ", expected[n-1], "\\n\\n");
    fi;
od;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s2_s6_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s2_s6_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S2-S6...")

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
    stdout, stderr = process.communicate(timeout=300)
    print(stdout)
    if stderr:
        print("STDERR:", stderr[:500])
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 5 minutes")
    sys.exit(1)

sys.exit(process.returncode)
