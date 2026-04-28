import subprocess, os, time
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_265.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

run = 0
while True:
    run += 1
    print(f"\n=== W265 run #{run} at {time.strftime('%H:%M:%S')} ===")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
    print(f"PID={process.pid}")
    stdout, stderr = process.communicate()
    print(f"Exited code={process.returncode}")
    if os.path.exists("parallel_s18/[4,4,4,2,2,2]/summary.txt"):
        print("Partition complete!")
        break
    print("Restarting in 5s...")
    time.sleep(5)
