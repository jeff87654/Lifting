import subprocess
import os
import time

gap_script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_recompute_4443_2.g"
log_file = r"C:\Users\jeffr\Downloads\Lifting\gap_recompute_4443_2.log"

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting [4,4,4,3,2] recompute at {time.strftime('%H:%M:%S')}")
print(f"Log: {log_file}")
print("This may take 60-120+ minutes with unlimited memory...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{gap_script}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)  # 2 hour timeout

print(f"\nFinished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

if os.path.exists(log_file):
    with open(log_file, "r") as f:
        log = f.read()
    # Print last 30 lines
    lines = log.strip().split('\n')
    print(f"\nLog ({len(lines)} lines), last 30:")
    for line in lines[-30:]:
        print(line)
else:
    print("No log file found!")
    if stdout.strip():
        print(f"stdout: {stdout[-500:]}")
    if stderr.strip():
        print(f"stderr: {stderr[-500:]}")
