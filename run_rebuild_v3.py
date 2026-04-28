import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/rebuild_gens_v2.g"
log_file = r"C:\Users\jeffr\Downloads\Lifting\rebuild_gens_v2.log"

# Remove old log
if os.path.exists(log_file):
    os.remove(log_file)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting rebuild v3 at {time.strftime('%H:%M:%S')}...")
# No -o flag this time
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

while process.poll() is None:
    time.sleep(30)
    if os.path.exists(log_file):
        with open(log_file, 'r', errors='replace') as f:
            content = f.read()
        wrote = content.count("Wrote ")
        warnings = content.count("WARNING")
        lines = len(content.split('\n'))
        print(f"  {time.strftime('%H:%M:%S')}: {wrote}/18 done, {warnings} warnings, {lines} lines")

stdout, stderr = process.communicate(timeout=14400)
print(f"Finished at {time.strftime('%H:%M:%S')}, rc={process.returncode}")

if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        log = f.read()
    for line in log.split('\n'):
        if any(x in line for x in ['Wrote', 'WARNING', 'Dedup', '===', 'Got ']):
            print(line)
else:
    print("No log file")
    print("STDOUT:", stdout[-1000:])
    print("STDERR:", stderr[-1000:])
