"""Test per-combo dedup change: verify S2-S10 counts match OEIS A000638."""
import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_dedup_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# OEIS A000638 reference values
expected := [1, 2, 4, 11, 19, 56, 96, 296, 554];

Print("=== Testing S2-S10 with per-combo dedup ===\\n");
startAll := Runtime();

for n in [2..10] do
    startN := Runtime();
    count := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startN) / 1000.0;
    exp := expected[n-1];
    if count = exp then
        Print("S", n, " = ", count, " PASS (", elapsed, "s)\\n");
    else
        Print("S", n, " = ", count, " FAIL (expected ", exp, ") (", elapsed, "s)\\n");
    fi;
od;

totalTime := (Runtime() - startAll) / 1000.0;
Print("\\nTotal time: ", totalTime, "s\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)

with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_dedup_test.log", "r") as f:
    log = f.read()
print(log)
