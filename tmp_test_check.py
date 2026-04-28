"""Test the check_combo_affected.g diagnostic on a handful of known cases."""
import subprocess, os

# Build a small test input: known-affected combos + a known-unaffected one
test_input = r"""# test input
[8,4,4,2]	[2,1]_[4,3]_[4,3]_[8,37].g	0
[8,4,4,2]	[2,1]_[4,3]_[4,3]_[8,49].g	0
[8,4,4,2]	[2,1]_[4,3]_[4,3]_[8,12].g	0
[6,4,4,2,2]	[2,1]_[2,1]_[4,3]_[4,3]_[6,11].g	0
[4,4,4,2,2]	[2,1]_[2,1]_[4,1]_[4,1]_[4,1].g	0
[6,4,4,2,2]	[2,1]_[2,1]_[4,1]_[4,3]_[6,9].g	0
"""
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_affected.txt", "w") as f:
    f.write(test_input)

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/check_test.log");
Read("C:/Users/jeffr/Downloads/Lifting/check_combo_affected.g");
ProcessAffectedList(
    "C:/Users/jeffr/Downloads/Lifting/tmp_test_affected.txt",
    "C:/Users/jeffr/Downloads/Lifting/tmp_test_result.txt");
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_check.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_check.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    o, e = p.communicate(timeout=600)
except subprocess.TimeoutExpired:
    p.kill(); o, e = p.communicate()

print("=== log ===")
try:
    print(open(r"C:\Users\jeffr\Downloads\Lifting\check_test.log").read())
except FileNotFoundError:
    print("(no log file)")
    print("STDOUT:", o[-1500:])
    print("STDERR:", e[-500:])

print()
print("=== results ===")
try:
    print(open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_result.txt").read())
except FileNotFoundError:
    print("(no result file)")
