"""Recompute the OOM combo from worker 6 with more memory."""
import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_recompute_oom.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting OOM combo recompute at {time.strftime('%H:%M:%S')}...")
print("Using -o 8g for 8GB memory limit")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_recompute_oom.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'Result' in line or 'Factor' in line or '|P|' in line or '|N|' in line or 'Memory' in line:
            print(line)
except FileNotFoundError:
    print("Log file not found, stdout:", stdout[:2000])
