import subprocess, os, sys
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1untime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1untimeinash.exe"
script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/worker_100.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1untimein;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
cmd = [BASH_EXE, "--login", "-c",
       'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "' + script_cygwin + '"']
process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=env, cwd=GAP_RUNTIME)
print(f"Launched gap via bash PID {process.pid}")
process.wait()
print(f"W100 exited with code {process.returncode}")
