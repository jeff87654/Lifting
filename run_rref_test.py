import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_rref_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("RREF Enumeration Test\\n");
Print("=====================\\n\\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;

for n in [2..10] do
    t := Runtime();
    r := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t) / 1000.0;
    if r = known[n] then
        Print("S", n, ": ", r, " PASS (", elapsed, "s)\\n");
    else
        Print("S", n, ": ", r, " FAIL (expected ", known[n], ") (", elapsed, "s)\\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\\nALL TESTS PASSED\\n");
else
    Print("\\nSOME TESTS FAILED\\n");
fi;

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

print("Running S2-S10 with RREF enumeration...")
print(f"Output logged to: {log_file}")

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
    stdout, stderr = process.communicate(timeout=3600)
except subprocess.TimeoutExpired:
    print("Timed out")
    process.kill()

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_rref_test.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(kw in line for kw in ['PASS', 'FAIL', 'Total S_', 'Final count', 'Time:', 'LiftThroughLayer', 'Partition', 'RREF', 'ALL']):
            print(line.strip())
else:
    print("Log not found")
    if stdout:
        print("stdout:", stdout[-2000:])
