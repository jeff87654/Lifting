import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s12_clean.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 clean run at {time.strftime('%H:%M:%S')}")
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
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_s12_clean.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'Partition' in line and ('classes' in line or '=>' in line):
            print(line.strip())
        elif 'S12' in line or 'PASS' in line or 'FAIL' in line or 'Total time' in line or 'Total S_' in line:
            print(line.strip())
        elif 'Time:' in line and 'Partition' not in line:
            print(line.strip())
except FileNotFoundError:
    print("Log not found")
    print(stdout[:5000] if stdout else "No stdout")
