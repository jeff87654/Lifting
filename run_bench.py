import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_bench.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting benchmark at {time.strftime('%H:%M:%S')}")
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
    stdout, stderr = process.communicate(timeout=600)
    print(f"Finished at {time.strftime('%H:%M:%S')}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_bench.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if line.strip():
            print(line)
except:
    print(stdout[:3000] if stdout else "No output")
