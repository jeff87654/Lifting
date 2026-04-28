import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/rerun_8_5_4.log"

gap_commands = f'''
LogTo("{log_file}");
Print("Starting [8,5,4] rerun at ", StringTime(Runtime()), "\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
Print("Caches loaded, starting computation at ", StringTime(Runtime()), "\\n");
result := FindFPFClassesForPartition(17, [8,5,4]);
Print("\\n=== RESULT ===\\n");
Print("FPF count for [8,5,4]: ", Length(result), "\\n");
Print("Expected (deduped .bak): 33260\\n");
Print("Finished at ", StringTime(Runtime()), "\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_rerun_8_5_4.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_rerun_8_5_4.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP computation for [8,5,4] at {time.strftime('%H:%M:%S')}")
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

stdout, stderr = process.communicate(timeout=36000)

print(f"\nGAP process finished at {time.strftime('%H:%M:%S')} with return code {process.returncode}")

if stderr.strip():
    print(f"STDERR: {stderr[:500]}")

# Read results from log file
try:
    with open(log_file, "r") as f:
        log = f.read()
    print(f"\nLog file size: {len(log)} bytes")
    print("\n--- Key lines from log ---")
    for line in log.split('\n'):
        if any(kw in line for kw in ['RESULT', 'FPF count', 'Expected', 'Starting', 'Finished', 'ERROR', 'Error']):
            print(line)
except FileNotFoundError:
    print("ERROR: Log file not found!")
