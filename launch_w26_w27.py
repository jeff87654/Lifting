import subprocess, os
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
for wid in [26, 27]:
    script = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_{wid}.g"
    proc = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script}"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=gap_runtime)
    print(f"Worker {wid} launched (bash PID {proc.pid})")
import time; time.sleep(2)
print("Both launched. Exiting launcher.")
