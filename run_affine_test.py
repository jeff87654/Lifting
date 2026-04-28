"""Test S2-S10 with the affine H^1 action fix."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/affine_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable orbital
USE_H1_ORBITAL := true;

# Expected OEIS A000638 values
expected := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

allPass := true;
for n in [2..10] do
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
    LIFT_CACHE := rec();

    t0 := Runtime();
    count := CountAllConjugacyClassesFast(n);
    t := Runtime() - t0;

    if count = expected[n] then
        Print("S", n, ": ", count, " OK (", t, "ms)\\n");
    else
        Print("S", n, ": ", count, " FAIL (expected ", expected[n], ") (", t, "ms)\\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\\nALL S2-S10 PASSED\\n");
else
    Print("\\nSOME TESTS FAILED\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_affine_test.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_affine_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 test with affine fix at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(x in line for x in ['S', 'PASS', 'FAIL', 'Error', 'error']):
            stripped = line.strip()
            if stripped and not stripped.startswith('Syntax') and not stripped.startswith('^'):
                print(stripped)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
