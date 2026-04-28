import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_28.g"

# Launch with 8GB memory limit (-o 8g) to avoid OOM on combo 58
proc = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script}"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=gap_runtime)
print(f"Worker 28 launched (bash PID {proc.pid}) with -o 8g memory limit")
time.sleep(2)
print("Done. Monitor worker_28_heartbeat.txt for progress.")
