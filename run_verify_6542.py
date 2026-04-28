import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/verify_6542.g"
log_file = r"C:\Users\jeffr\Downloads\Lifting\verify_6542.log"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting verification at {time.strftime('%H:%M:%S')}...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)  # 4 hour timeout

print(f"Finished at {time.strftime('%H:%M:%S')}")

if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        log = f.read()
    print(log[-5000:] if len(log) > 5000 else log)
else:
    print("No log file generated")
    print("STDOUT:", stdout[-2000:])
    print("STDERR:", stderr[-2000:])
