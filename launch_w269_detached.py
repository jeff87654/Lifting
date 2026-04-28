"""Launch w269 fully detached so it survives this Python script's exit."""
import subprocess
import os
import sys

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_269.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

os.makedirs(
    r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\checkpoints\worker_269",
    exist_ok=True)

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB

print("Launching worker 269 (detached)...")
sys.stdout.flush()

proc = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" '
     f'&& ./gap.exe -q -o 0 "{script_path}"'],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    env=env,
    cwd=gap_runtime,
    creationflags=flags,
    close_fds=True,
)
print(f"Launched: PID {proc.pid}")
print("Monitor: cat parallel_s18/worker_269_heartbeat.txt")
