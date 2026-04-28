"""Launch worker 506 as an independent background GAP process."""
import subprocess, os

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_506.g"

p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script}"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched worker 506 at PID {p.pid}")
print(f"Log: C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_506.log")
print(f"Heartbeat: C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_506_heartbeat.txt")
