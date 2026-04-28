"""Test all S12 FPF partitions against ground truth."""
import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s12_all.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 full test at {time.strftime('%H:%M:%S')}...")
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
stdout, stderr = p.communicate(timeout=3600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

with open(r"C:\Users\jeffr\Downloads\Lifting\test_s12_all.log", "r") as f:
    for line in f.read().strip().split('\n'):
        if any(kw in line for kw in ['PASS', 'FAIL', 'failure', 'total', 'Expected']):
            print(line)
