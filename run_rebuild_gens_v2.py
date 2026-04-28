import subprocess
import os
import time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/rebuild_gens_v2.g"
log_file = r"C:\Users\jeffr\Downloads\Lifting\rebuild_gens_v2.log"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting rebuild v2 at {time.strftime('%H:%M:%S')}...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

# Monitor progress
while process.poll() is None:
    time.sleep(30)
    if os.path.exists(log_file):
        with open(log_file, 'r', errors='replace') as f:
            content = f.read()
        rebuilding = content.count("=== Rebuilding")
        wrote = content.count("Wrote ")
        warnings = content.count("WARNING")
        print(f"  {time.strftime('%H:%M:%S')}: {wrote}/18 partitions done, {warnings} warnings")

stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}, rc={process.returncode}")

if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        log = f.read()
    # Show summary lines
    for line in log.split('\n'):
        if 'Wrote' in line or 'WARNING' in line or 'Dedup' in line or '===' in line:
            print(line)
else:
    print("No log file")
    print("STDOUT:", stdout[-2000:])
    print("STDERR:", stderr[-2000:])
