"""Launch all 4 workers detached after the reboot. Each worker resumes
from its own checkpoint, skipping combos whose output files already exist."""
import subprocess
import os
import sys

WORKERS = [266, 267, 268, 269]

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB

for wn in WORKERS:
    ckpt_dir = rf"C:\Users\jeffr\Downloads\Lifting\parallel_s18\checkpoints\worker_{wn}"
    os.makedirs(ckpt_dir, exist_ok=True)
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wn}.g"

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
    print(f"Launched worker {wn}: PID {proc.pid}")
    sys.stdout.flush()

print("\nAll 4 workers launched. Monitor heartbeats:")
for wn in WORKERS:
    print(f"  parallel_s18/worker_{wn}_heartbeat.txt")
