import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s13b.log"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

# Use cached S12 data and only compute S13
# Also flush log before writing totals
gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== S13 Performance Test (v2) ===\\n");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
CountAllConjugacyClassesFast(13);

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S13 test (v2)...")
print(f"Log file: {log_file}")
start = time.time()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=43200)
elapsed = time.time() - start
print(f"GAP finished in {elapsed:.1f}s ({elapsed/3600:.2f} hours)")
print(f"Exit code: {process.returncode}")

# Print ALL stdout (not just filtered)
if stdout.strip():
    # Find the important lines in stdout
    for line in stdout.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ['Total S_13', 'Total S_12', 'Time:', 'Error',
                                      'FAIL', '=> ', 'Partition [']):
            print(f"[stdout] {line}")

# Print non-warning stderr
if stderr.strip():
    for line in stderr.split('\n'):
        if 'Syntax warning' not in line and line.strip():
            print(f"[stderr] {line}")

# Read log and print summary
try:
    with open(log_file, "r") as f:
        log = f.read()

    print(f"\nLog file: {len(log.splitlines())} lines")

    # Print partition results and totals
    for line in log.split('\n'):
        if any(kw in line for kw in ['Total S_13', 'Total S_12']):
            print(f"[log] {line.strip()}")

    # Print last 30 lines of log for context
    print("\n--- Last 30 lines of log ---")
    for line in log.split('\n')[-30:]:
        print(line.rstrip())
except Exception as e:
    print(f"Error reading log: {e}")
