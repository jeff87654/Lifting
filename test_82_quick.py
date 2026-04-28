import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_82_quick.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear ALL caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("All caches cleared.\\n\\n");

# Pre-populate lower S_n values so we only measure S10's [8,2]
CountAllConjugacyClassesFast(8);
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Now test just the [8,2] partition timing
Print("\\n=== Testing [8,2] partition for S10 ===\\n");
startTime := Runtime();
result := FindFPFClassesForPartition(10, [8, 2]);
Print("[8,2] count: ", Length(result), "\\n");
Print("[8,2] time: ", (Runtime() - startTime) / 1000.0, "s\\n");

# Also test [4,2,2,2] which was another big bottleneck
Print("\\n=== Testing [4,2,2,2] partition for S10 ===\\n");
startTime := Runtime();
result := FindFPFClassesForPartition(10, [4, 2, 2, 2]);
Print("[4,2,2,2] count: ", Length(result), "\\n");
Print("[4,2,2,2] time: ", (Runtime() - startTime) / 1000.0, "s\\n");

# Test [4,4,2]
Print("\\n=== Testing [4,4,2] partition for S10 ===\\n");
startTime := Runtime();
result := FindFPFClassesForPartition(10, [4, 4, 2]);
Print("[4,4,2] count: ", Length(result), "\\n");
Print("[4,4,2] time: ", (Runtime() - startTime) / 1000.0, "s\\n");

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

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}...")
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
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_82_quick.log", "r") as f:
        log = f.read()
    # Just print last portion with results
    lines = log.split('\n')
    for line in lines:
        if any(k in line for k in ['===', 'count:', 'time:', 'Testing']):
            print(line)
except FileNotFoundError:
    print("Log file not found. Stdout:")
    print(stdout[-2000:])
