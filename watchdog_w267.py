import subprocess, os, time, sys

wid = int(sys.argv[1]) if len(sys.argv) > 1 else 267
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wid}.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

run = 0
while True:
    run += 1
    print(f"\n=== W{wid} run #{run} at {time.strftime('%H:%M:%S')} ===")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
    print(f"PID={process.pid}")
    stdout, stderr = process.communicate()
    print(f"Exited code={process.returncode}")
    # Check heartbeat for completion
    hb = f"parallel_s18/worker_{wid}_heartbeat.txt"
    if os.path.exists(hb):
        with open(hb) as f:
            if "completed partition" in f.read() and "RESTART" not in open(hb).read():
                pass  # might be done with one partition but not all
    print("Restarting in 5s...")
    time.sleep(5)
