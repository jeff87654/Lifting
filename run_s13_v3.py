import subprocess
import os
import time
import sys

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s13c.log"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

# Add sentinel markers and memory info to detect crashes
gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== S13 Performance Test (v3) ===\\n");
Print("GAP memory: ", GasmanStatistics(), "\\n");

FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("STARTING S13 COMPUTATION\\n");
CountAllConjugacyClassesFast(13);
Print("S13 COMPUTATION COMPLETE\\n");

Print("GAP memory at end: ", GasmanStatistics(), "\\n");

LogTo();
Print("LOG CLOSED SUCCESSFULLY\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S13 test (v3) with crash detection...")
print(f"Log file: {log_file}")
start = time.time()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=43200)
elapsed = time.time() - start
print(f"\nGAP finished in {elapsed:.1f}s ({elapsed/3600:.2f} hours)")
print(f"Exit code: {process.returncode}")

# Print ALL of stdout (not filtered)
print(f"\n=== STDOUT ({len(stdout.splitlines())} lines) ===")
# Print first 10 and last 50 lines
stdout_lines = stdout.splitlines()
if len(stdout_lines) > 60:
    for line in stdout_lines[:10]:
        print(line)
    print(f"... ({len(stdout_lines) - 60} lines omitted) ...")
    for line in stdout_lines[-50:]:
        print(line)
else:
    print(stdout)

# Print non-warning stderr
print("\n=== STDERR (non-warnings) ===")
for line in stderr.split('\n'):
    if 'Syntax warning' not in line and 'Unbound global' not in line and line.strip() and '^' not in line:
        print(f"  {line}")

# Check log file
try:
    with open(log_file, "r") as f:
        log = f.read()
    log_lines = log.splitlines()
    print(f"\n=== LOG FILE: {len(log_lines)} lines ===")

    # Check for sentinels
    for sentinel in ['STARTING', 'COMPLETE', 'Total S_13', 'Total S_12']:
        found = [i for i, l in enumerate(log_lines) if sentinel in l]
        if found:
            print(f"  Found '{sentinel}' at line(s): {found}")
        else:
            print(f"  '{sentinel}' NOT FOUND")

    # Print last 20 lines
    print("\n--- Last 20 lines of log ---")
    for line in log_lines[-20:]:
        print(line)
except Exception as e:
    print(f"Error reading log: {e}")
