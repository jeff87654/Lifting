import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_breakdown.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Pre-populate S8
CountAllConjugacyClassesFast(8);
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("\\n=== Profiling S10 bottleneck partitions ===\\n\\n");

# Test each bottleneck partition
for part in [[4,4,2], [4,2,2,2], [2,2,2,2,2], [3,3,2,2], [6,4]] do
    Print("--- Partition ", part, " ---\\n");
    startTime := Runtime();
    result := FindFPFClassesForPartition(10, part);
    Print("  Result: ", Length(result), " classes in ", (Runtime() - startTime) / 1000.0, "s\\n\\n");
od;

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

print(f"Starting breakdown test at {time.strftime('%H:%M:%S')}...")
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

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_breakdown.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(k in line for k in ['===', '---', 'LiftThroughLayer', 'Result:', 'Partition', 'breakdown']):
            print(line)
except FileNotFoundError:
    print("Log file not found.")
    print(stdout[-3000:])
