import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/worker_96.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Launching W96 [4,2,2,2,2,2,2] at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [BASH_EXE, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=86400)
print(f"W96 finished at {time.strftime('%H:%M:%S')} (rc={process.returncode})")

result_file = os.path.join(LIFTING_DIR, "parallel_s16", "worker_96_results.txt")
if os.path.exists(result_file):
    with open(result_file) as f:
        print(f"Result: {f.read().strip()}")
else:
    print("No result file")
