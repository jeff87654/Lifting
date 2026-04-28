import subprocess, os, sys

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_s17_slow_combo_holt.g"
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
# No timeout - this may take up to 90 minutes if Holt is similar; we'll watch the log
try:
    out, err = p.communicate(timeout=90*60)
except subprocess.TimeoutExpired:
    p.kill()
    print("TIMEOUT - killed after 90 minutes")
    sys.exit(1)

print("stdout tail:")
print((out or "")[-2000:])
print("stderr tail:")
print((err or "")[-2000:])
