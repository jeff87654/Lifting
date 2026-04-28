import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_full_v2.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear ALL caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("All caches cleared.\\n");
Print("CROSS_VALIDATE_COCYCLES = ", CROSS_VALIDATE_COCYCLES, "\\n\\n");

# Full S10 test from scratch
Print("=== Full S10 from scratch ===\\n");
startTime := Runtime();
result10 := CountAllConjugacyClassesFast(10);
Print("\\nS10 total: ", result10, " (expected 1593)\\n");
Print("S10 total time: ", (Runtime() - startTime) / 1000.0, "s\\n\\n");

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

print(f"Starting full S10 test at {time.strftime('%H:%M:%S')}...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_full_v2.log", "r") as f:
        log = f.read()
    # Print partition timings and totals
    for line in log.split('\n'):
        if any(k in line for k in ['Partition', 'Time:', 'Total', 'total', 'count:', 'expected', 'CROSS_VALIDATE', 'cleared', '===']):
            print(line)
except FileNotFoundError:
    print("Log file not found. Stdout:")
    print(stdout[-2000:])
