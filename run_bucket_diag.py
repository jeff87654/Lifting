import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_bucket_diag.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting bucket diagnostics at {time.strftime('%H:%M:%S')}")
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
    print(f"Finished at {time.strftime('%H:%M:%S')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 1 hour")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_bucket_diag.log", "r") as f:
        log = f.read()
    # Print the results section
    in_results = False
    for line in log.split('\n'):
        if '=== Results ===' in line or '=== Bucket' in line:
            in_results = True
        if in_results:
            print(line.strip())
        elif 'combo' in line and 'candidates' in line:
            print(line.strip())
except FileNotFoundError:
    print("Log not found")
    print(stdout[:5000] if stdout else "No stdout")
