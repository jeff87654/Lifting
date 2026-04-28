"""
Test S7-S8.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

expected := rec();
expected.("7") := 96;
expected.("8") := 296;

for n in [7..8] do
    Print("Testing S", n, "...\\n");
    count := CountAllConjugacyClassesFast(n);
    Print("S", n, " conjugacy classes: ", count, "\\n");
    if count = expected.(String(n)) then
        Print("PASS\\n\\n");
    else
        Print("FAIL: expected ", expected.(String(n)), "\\n\\n");
    fi;
od;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s7_s8_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s7_s8_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing S7-S8...")

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
        print("STDERR:", stderr[:500])
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 10 minutes")
    sys.exit(1)

sys.exit(process.returncode)
