import subprocess, os, time

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_264.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

run = 0
while True:
    run += 1
    print(f"\n=== W264 run #{run} at {time.strftime('%H:%M:%S')} ===")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
    print(f"PID={process.pid}")
    stdout, stderr = process.communicate()
    print(f"Exited code={process.returncode}")
    # Check if all partitions done
    all_done = True
    for p in ["[6,4,4,4]","[12,6]","[6,4,3,3,2]","[8,5,5]","[5,4,4,3,2]","[5,5,4,4]",
              "[6,4,2,2,2,2]","[9,3,3,3]","[7,5,4,2]","[10,3,3,2]","[14,4]","[9,3,2,2,2]",
              "[6,3,3,3,3]","[11,7]","[11,3,2,2]","[3,3,3,3,2,2,2]","[18]"]:
        summary = os.path.join("parallel_s18", p, "summary.txt")
        if not os.path.exists(summary):
            all_done = False
            break
    if all_done:
        print("All partitions complete!")
        break
    print("Restarting in 5s...")
    time.sleep(5)
