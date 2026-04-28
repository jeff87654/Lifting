import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_s11_bisect_output.txt"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the FPF cache to force fresh computation
FPF_SUBDIRECT_CACHE := rec();

Print("\\n=== S11 Bisection Test ===\\n");
Print("Testing with H^1 orbital OFF and C2 orbit reduction still ON\\n\\n");

# Disable H^1 orbital to test if that's the cause
USE_H1_ORBITAL := false;

result := CountAllConjugacyClassesFast(11);
Print("\\n========================================\\n");
Print("S11 count (orbital OFF): ", result, "\\n");
Print("Expected: 3094\\n");
if result = 3094 then
    Print("H^1 orbital was the problem\\n");
elif result = 3079 then
    Print("H^1 orbital NOT the problem - issue is elsewhere\\n");
else
    Print("Different count: ", result, "\\n");
fi;
Print("========================================\\n");

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

print("Running S11 bisection test (H^1 orbital OFF)...")

wall_start = time.time()

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
    wall_end = time.time()
    print(f"Wall clock time: {wall_end - wall_start:.1f}s ({(wall_end - wall_start)/60:.1f} min)")
except subprocess.TimeoutExpired:
    process.kill()
    print("Timed out")
