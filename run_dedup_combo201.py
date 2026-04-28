import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

script = os.path.join(LIFTING_DIR, "dedup_combo201.g")
script_cygwin = script.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print("Launching dedup...", flush=True)
start = time.time()
p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=GAP_RUNTIME)
print(f"PID: {p.pid}", flush=True)

try:
    p.wait(timeout=600)
    print(f"Done in {time.time()-start:.0f}s", flush=True)
except subprocess.TimeoutExpired:
    p.kill()
    print("TIMEOUT", flush=True)

log = os.path.join(LIFTING_DIR, "dedup_combo201.log")
if os.path.exists(log):
    with open(log) as f:
        print(f.read(), flush=True)
