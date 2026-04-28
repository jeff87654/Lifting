import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s12.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t := Runtime();
r := CountAllConjugacyClassesFast(12);
Print("\\nS12 time: ", (Runtime() - t) / 1000.0, "s\\n");
Print("S12 result: ", r, "\\n");
Print("Expected: 10723\\n");
if r = 10723 then Print("PASS\\n"); else Print("FAIL\\n"); fi;
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

print("Running S12...")
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
    stdout, stderr = process.communicate(timeout=7200)
except subprocess.TimeoutExpired:
    print("Timed out after 2 hours")
    process.kill()

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_s12.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(kw in line for kw in ['PASS', 'FAIL', 'S12', 'Total S_', 'Final count', 'Time:', 'LiftThroughLayer', 'Partition']):
            print(line.strip())
else:
    print("Log not found")
    if stdout:
        print("stdout:", stdout[-2000:])
