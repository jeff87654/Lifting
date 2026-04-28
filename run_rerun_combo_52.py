import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/rerun_combo_52.log"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/rerun_combo_52.g"

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Run GAP via Cygwin bash with -o 8g for 8GB memory
cmd = [
    bash_exe, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script_path}"'
]

print(f"Starting GAP with 8GB memory limit...")
print(f"Script: {script_path}")
print(f"Log: {log_file}")
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=3600)
    print(f"\nGAP finished with return code: {process.returncode}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if stderr:
        print(f"Stderr: {stderr[:500]}")
except subprocess.TimeoutExpired:
    process.kill()
    print("GAP TIMED OUT after 3600 seconds!")

# Read results from the log file
try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\rerun_combo_52.log", "r") as f:
        log = f.read()
    print("\n=== LOG OUTPUT ===")
    print(log[-3000:] if len(log) > 3000 else log)
except FileNotFoundError:
    print("Log file not found!")
