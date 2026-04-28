import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s12_bench2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 benchmark v2 at {time.strftime('%H:%M:%S')}")
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
    print(f"Return code: {process.returncode}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 2 hours")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_s12_bench2.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['PASS', 'FAIL', 'Time', 'time', '===',
                'expected', 'Total', 'S12', 'Partition', 'Grand', 'classes',
                'Loaded']):
            print(line.strip())
except FileNotFoundError:
    print("Log not found")
    if stdout:
        print("STDOUT:", stdout[:3000])
    if stderr:
        print("STDERR:", stderr[:3000])
