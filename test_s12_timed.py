import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_s12_timed_output.txt"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the FPF cache to force fresh computation
FPF_SUBDIRECT_CACHE := rec();

ResetH1OrbitalStats();

result := CountAllConjugacyClassesFast(12);
Print("\\n========================================\\n");
Print("S12 conjugacy class count: ", result, "\\n");
Print("Expected: 334 (OEIS A018216 for n=12: not confirmed)\\n");
Print("========================================\\n\\n");

PrintH1OrbitalStats();

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

print(f"Running S12 full timed test...")
print(f"Output: {log_file}")

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
    stdout, stderr = process.communicate(timeout=36000)  # 10 hour timeout
    wall_end = time.time()
    print(f"\nWall clock time: {wall_end - wall_start:.1f}s ({(wall_end - wall_start)/60:.1f} min)")
except subprocess.TimeoutExpired:
    process.kill()
    print("Timed out after 10 hours")
