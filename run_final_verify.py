import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_final_verify.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;

# Quick check S2-S9
for n in [2..9] do
    FPF_SUBDIRECT_CACHE := rec();
    LIFT_CACHE := rec();
    result := CountAllConjugacyClassesFast(n);
    if result <> known[n] then
        Print("FAIL: S_", n, " got ", result, " expected ", known[n], "\\n");
        allPass := false;
    else
        Print("S_", n, ": PASS (", result, ")\\n");
    fi;
od;

# Timed S10
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t := Runtime();
r := CountAllConjugacyClassesFast(10);
t10 := (Runtime() - t) / 1000.0;
if r <> known[10] then
    Print("FAIL: S_10 got ", r, " expected ", known[10], "\\n");
    allPass := false;
else
    Print("S_10: PASS (", r, ")\\n");
fi;
Print("S10 time: ", t10, "s\\n");

if allPass then
    Print("\\nALL S2-S10 PASSED\\n");
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

print("Final verification S2-S10 with timing...")

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
    stdout, stderr = process.communicate(timeout=1800)
except subprocess.TimeoutExpired:
    print("Timed out after 30 minutes")
    process.kill()
    stdout, stderr = process.communicate()

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_final_verify.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(kw in line for kw in ['PASS', 'FAIL', 'S10 time', 'ALL', 'SOME']):
            print(line.strip())
else:
    print("Log not found")
    if stdout:
        print("stdout:", stdout[-2000:])
