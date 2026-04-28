import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/rerun_6_5_4_2.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
Print("\\n=== Starting [6,5,4,2] computation ===\\n");
Print("Time: ", StringTime(Runtime()), "\\n");
result := FindFPFClassesForPartition(17, [6,5,4,2]);
Print("\\n=== RESULT ===\\n");
Print("FPF count for [6,5,4,2]: ", Length(result), "\\n");
Print("Expected (deduped .bak): 26826\\n");
Print("Time: ", StringTime(Runtime()), "\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_rerun_6_5_4_2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_rerun_6_5_4_2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP computation for [6,5,4,2]...")
print(f"Log file: {log_file}")
print(f"Timeout: 36000s (10 hours)")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=36000)
    print(f"GAP process finished with return code: {process.returncode}")
    if stderr.strip():
        print(f"stderr: {stderr[:500]}")
except subprocess.TimeoutExpired:
    process.kill()
    print("GAP process timed out after 10 hours!")

# Read results from log file
try:
    with open(log_file, "r") as f:
        log = f.read()
    print(f"\nLog file size: {len(log)} bytes")
    print("\n=== Key results from log ===")
    for line in log.split('\n'):
        if any(kw in line for kw in ['RESULT', 'FPF count', 'Expected', 'Starting', 'Time:']):
            print(line)
except FileNotFoundError:
    print(f"Log file not found: {log_file}")
