"""Launch workers 23 and 24 for reassigned partitions."""
import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

processes = []
for wid in [23, 24]:
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_{wid}.g"
    cmd = [
        bash_exe, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )
    print(f"Worker {wid} launched (PID {proc.pid})")
    processes.append((wid, proc))
    time.sleep(2)

print(f"\nBoth workers launched. Waiting for completion...")

for wid, proc in processes:
    stdout, stderr = proc.communicate(timeout=86400)
    print(f"Worker {wid} finished (exit code {proc.returncode})")
    if os.path.exists(f"C:/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_{wid}_results.txt"):
        with open(f"C:/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_{wid}_results.txt") as f:
            print(f"  Results: {f.read().strip()}")

print("\nDone!")
