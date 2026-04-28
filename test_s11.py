import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s11.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear ALL caches for fresh computation
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("All caches cleared.\\n\\n");

# Full S11 from scratch
Print("=== Full S11 from scratch ===\\n");
startTime := Runtime();
result11 := CountAllConjugacyClassesFast(11);
Print("\\nS11 total: ", result11, " (expected 3094)\\n");
Print("S11 total time: ", (Runtime() - startTime) / 1000.0, "s\\n\\n");

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

print(f"Starting S11 test at {time.strftime('%H:%M:%S')}...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_s11.log", "r") as f:
        log = f.read()
    print("=== GAP Output (key lines) ===")
    for line in log.split('\n'):
        if any(k in line for k in ['Partition', 'Time:', 'Total', 'total', 'count:',
                                     'expected', 'cleared', '===', 'S11', 'S10', 'S9', 'S8',
                                     'LiftThroughLayer', 'time:']):
            print(line)
except FileNotFoundError:
    print("Log file not found. Stdout:")
    print(stdout[-3000:])

if stderr:
    print("=== Stderr (last 500 chars) ===")
    print(stderr[-500:])
