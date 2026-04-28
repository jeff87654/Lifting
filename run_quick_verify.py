import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_quick_verify.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting quick verify at {time.strftime('%H:%M:%S')}")
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
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_quick_verify.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'PASS' in line or 'FAIL' in line or 'time' in line or 'Total' in line:
            print(line.strip())
except FileNotFoundError:
    print("Log not found")
    print(stdout[:5000] if stdout else "No stdout")
