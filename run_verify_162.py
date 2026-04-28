import subprocess, os, sys
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_162_combos.g"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
try: out, err = p.communicate(timeout=30*60)
except subprocess.TimeoutExpired:
    p.kill(); print("TIMEOUT"); sys.exit(1)
print((out or "")[-3500:])
