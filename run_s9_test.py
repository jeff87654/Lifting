import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/test_s9_only.g");
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S9 test...")
print("=" * 50)

start = time.time()

# Run GAP via Cygwin bash with longer timeout
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=1800)  # 30 minute timeout

elapsed = time.time() - start

print(stdout)
if stderr:
    print("STDERR:", stderr)

print("=" * 50)
print(f"Total test time: {elapsed:.2f}s")
