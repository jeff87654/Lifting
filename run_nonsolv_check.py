import subprocess, os
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/check_nonsolv_pairs.g"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && exec ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=gap_runtime,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)
print(f"PID={p.pid}")
