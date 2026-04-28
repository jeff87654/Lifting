import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/rerun_6_4_3_2_2.log"

# Write the GAP script (no date call - it errors in GAP)
gap_commands = f'''LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
startTime := Runtime();
result := FindFPFClassesForPartition(17, [6,4,3,2,2]);
elapsed := Runtime() - startTime;
Print("\\n=== RESULT ===\\n");
Print("FPF count for [6,4,3,2,2]: ", Length(result), "\\n");
Print("Expected (deduped .bak): 59732\\n");
Print("Elapsed time: ", Int(elapsed/1000), "s\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_rerun_6_4_3_2_2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_rerun_6_4_3_2_2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP computation at {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Log file: {log_file}")
print("This may take several hours...")

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

print(f"\nGAP process finished at {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Return code: {process.returncode}")

if stderr.strip():
    print(f"Stderr: {stderr[:500]}")

# Read results from the LogTo file
try:
    with open(log_file, "r") as f:
        log = f.read()

    print("\n--- Key results from log ---")
    for line in log.split('\n'):
        if any(kw in line for kw in ['RESULT', 'FPF count', 'Expected', 'Elapsed time']):
            print(line)

    print(f"\nFull log size: {len(log)} characters, {log.count(chr(10))} lines")
except FileNotFoundError:
    print("Log file not found! GAP may have crashed before writing output.")
    print(f"Stdout: {stdout[:1000]}")
