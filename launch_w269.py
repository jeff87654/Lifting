import subprocess, os, sys

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_269.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Ensure checkpoint dir exists
os.makedirs(r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\checkpoints\worker_269", exist_ok=True)

print("Launching worker 269 (26 partitions, S_n fast path re-run)...")
sys.stdout.flush()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)

print(f"PID: {process.pid}")
print("Worker running in background. Monitor with:")
print("  cat parallel_s18/worker_269_heartbeat.txt")
print("  tail -f parallel_s18/worker_269.log")
