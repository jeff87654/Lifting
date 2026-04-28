"""Run S13 ground truth test."""
import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s13_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S13 test at {time.strftime('%H:%M:%S')}...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 4g "{script}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=3600)
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_s13_test.log", "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'PASS' in line or 'FAIL' in line or 'Summary' in line or 'Total' in line or 'Difference' in line or 'Failures' in line or '===' in line:
            print(line)
except FileNotFoundError:
    print("Log file not found, stdout:", stdout[:2000])
