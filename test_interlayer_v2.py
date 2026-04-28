"""Test inter-layer dedup v2 (P-based RA, bucket cap, DerivedLength invariant)."""
import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_interlayer_v2.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting test at {time.strftime('%H:%M:%S')}...")
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
stdout, stderr = p.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

log_file = r"C:\Users\jeffr\Downloads\Lifting\test_interlayer_v2.log"
with open(log_file, "r") as f:
    for line in f.read().strip().split('\n'):
        if any(kw in line for kw in ['S10', 'PASS', 'FAIL', '[6,4,2]', 'Inter-layer', 'time =']):
            print(line)
