import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_bfs_opt.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Launching BFS optimization test at {time.strftime('%H:%M:%S')}")
proc = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 4g "{script_path}" 2>&1'],
    stdout=open(os.path.join(LIFTING_DIR, "test_bfs_opt_stdout.txt"), "w"),
    stderr=subprocess.STDOUT,
    env=env,
    cwd=gap_runtime
)
print(f"Test PID: {proc.pid}")
print("Waiting for completion (timeout 10 min)...")
try:
    proc.wait(timeout=600)
    print(f"Test completed with return code {proc.returncode}")
except subprocess.TimeoutExpired:
    print("TIMEOUT after 10 minutes!")
    proc.kill()

log_file = os.path.join(LIFTING_DIR, "test_bfs_opt.log")
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        log = f.read()
    print("\n=== TEST LOG ===")
    print(log[-3000:] if len(log) > 3000 else log)
else:
    print("No log file found! Check stdout:")
    stdout_file = os.path.join(LIFTING_DIR, "test_bfs_opt_stdout.txt")
    if os.path.exists(stdout_file):
        with open(stdout_file, "r") as f:
            print(f.read()[-3000:])
