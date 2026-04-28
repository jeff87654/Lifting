import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_phase2_nocache.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear ALL caches to force fresh computation
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("All caches cleared.\\n\\n");

Print("USE_H1_COMPLEMENTS = ", USE_H1_COMPLEMENTS, "\\n");
Print("USE_H1_ORBITAL = ", USE_H1_ORBITAL, "\\n");
Print("CROSS_VALIDATE_COCYCLES = ", CROSS_VALIDATE_COCYCLES, "\\n\\n");

# Test S8 (expected: 296 per OEIS A000638)
Print("=== Testing S8 ===\\n");
startTime := Runtime();
result8 := CountAllConjugacyClassesFast(8);
Print("S8 total: ", result8, " (expected 296)\\n");
Print("S8 time: ", Runtime() - startTime, " ms\\n\\n");

# Test S9 (expected: 554)
Print("=== Testing S9 ===\\n");
# Clear again to force fresh S9 computation (S8 is cached from above)
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
startTime := Runtime();
result9 := CountAllConjugacyClassesFast(9);
Print("S9 total: ", result9, " (expected 554)\\n");
Print("S9 time: ", Runtime() - startTime, " ms\\n\\n");

# Test S10 (expected: 1593)
Print("=== Testing S10 ===\\n");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
startTime := Runtime();
result10 := CountAllConjugacyClassesFast(10);
Print("S10 total: ", result10, " (expected 1593)\\n");
Print("S10 time: ", Runtime() - startTime, " ms\\n\\n");

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

print(f"Starting GAP tests (no cache) at {time.strftime('%H:%M:%S')}...")
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
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_phase2_nocache.log", "r") as f:
        log = f.read()
    print("=== GAP Output ===")
    print(log)
except FileNotFoundError:
    print("Log file not found. Stdout:")
    print(stdout)

if stderr:
    print("=== Stderr (last 1000 chars) ===")
    print(stderr[-1000:])
