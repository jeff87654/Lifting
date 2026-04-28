import subprocess, os, sys
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/rerun_bogus_combo.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
print("Rerunning [2,1]_[5,5]_[5,5]_[6,5] combo of [6,5,5,2] with fresh code...")
sys.stdout.flush()
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
try:
    stdout, stderr = process.communicate(timeout=7200)
except subprocess.TimeoutExpired:
    process.kill()
    stdout, stderr = process.communicate()
    print("TIMEOUT after 2h")
print(f"Exit: {process.returncode}")
if stderr.strip():
    print("STDERR:", stderr[-2000:])
print("--- log ---")
try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\rerun_bogus_combo.log") as f:
        print(f.read())
except Exception as e:
    print(f"Could not read log: {e}")
