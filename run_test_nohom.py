"""Run S2-S10 with USE_GENERAL_AUT_HOM disabled to isolate whether the
MovedPoints error is from our new code or pre-existing."""
import subprocess, os, sys

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_output_nohom.txt");
Print("S2-S10 Test (USE_GENERAL_AUT_HOM := false)\\n");
Print("==============================================\\n\\n");

# Disable the new path BEFORE reading code that defines it.
USE_GENERAL_AUT_HOM := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

for n in [2..10] do
    Print("\\nTesting S_", n, " (expected: ", known[n], ")\\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    if result = known[n] then
        Print("Status: PASS (", elapsed, "s)\\n");
    else
        Print("Status: FAIL: got ", result, " expected ", known[n], " (", elapsed, "s)\\n");
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_commands_nohom.g", "w") as f:
    f.write(gap_commands)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_commands_nohom.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=600)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()
