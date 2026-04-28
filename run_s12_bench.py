import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s12_bench.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 benchmark at {time.strftime('%H:%M:%S')}")
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
    print(f"Finished at {time.strftime('%H:%M:%S')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 2 hours")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_s12_bench.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'PASS' in line or 'FAIL' in line or 'Time' in line or 'time' in line or \
           '===' in line or 'expected' in line or 'Total' in line or \
           'S1' in line or 'S2' in line or 'S3' in line or 'S4' in line or \
           'S5' in line or 'S6' in line or 'S7' in line or 'S8' in line or \
           'S9' in line or 'Grand' in line:
            print(line.strip())
except FileNotFoundError:
    print("Log not found")
    print(stdout[:5000] if stdout else "No stdout")
