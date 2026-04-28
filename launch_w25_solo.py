import subprocess, os
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16_fresh/worker_25.g"
cmd = [bash_exe, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"']
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=gap_runtime)
print(f"Worker 25 launched (bash PID {proc.pid})")
proc.wait(timeout=86400)
print(f"Worker 25 finished (exit code {proc.returncode})")
