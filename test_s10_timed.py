import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the FPF cache to force fresh computation
FPF_SUBDIRECT_CACHE := rec();

ResetH1OrbitalStats();

result := CountAllConjugacyClassesFast(10);
Print("\\n========================================\\n");
Print("S10 conjugacy class count: ", result, "\\n");
Print("Expected: 1593\\n");
if result = 1593 then
    Print("SUCCESS\\n");
else
    Print("MISMATCH\\n");
fi;
Print("========================================\\n\\n");

PrintH1OrbitalStats();

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

log_file = r"C:\Users\jeffr\Downloads\Lifting\test_s10_timed_output.txt"

print(f"Running S10 full timed test...")
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
    stdout, stderr = process.communicate(timeout=3600)
    wall_end = time.time()

    with open(log_file, "w") as f:
        f.write(stdout)

    print(f"\nWall clock time: {wall_end - wall_start:.1f}s\n")

    # Print summary lines
    for line in stdout.split('\n'):
        if any(k in line for k in ['Total S_', 'Time:', 'S10 count', 'SUCCESS', 'MISMATCH',
                                     'Partition', 'Final count', '=> ', 'Orbital Statistics',
                                     'Orbital method', 'orbits computed', 'points', 'Reduction',
                                     '=====', 'Speedup']):
            print(line)

except subprocess.TimeoutExpired:
    process.kill()
    print("Timed out after 1 hour")
