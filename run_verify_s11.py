"""
Run S11 verification after optimization changes.
Uses precomputed S1-S10 cache to skip recomputation.
"""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_verify_s11.log"

gap_commands = f'''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF cache but keep LIFT_CACHE (has S1-S10)
FPF_SUBDIRECT_CACHE := rec();
# Reset S11 if cached
Unbind(LIFT_CACHE.("11"));
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

PrintTo("{log_file}", "S11 verification test\\n");
AppendTo("{log_file}", "========================================\\n\\n");

t0 := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := Runtime() - t0;

if result = 3094 then
    AppendTo("{log_file}", "S_11: PASS (", result, ") in ", elapsed/1000.0, "s\\n");
else
    AppendTo("{log_file}", "S_11: FAIL (got ", result, ", expected 3094) in ", elapsed/1000.0, "s\\n");
fi;
AppendTo("{log_file}", "========================================\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

try:
    os.remove(r"C:\Users\jeffr\Downloads\Lifting\gap_verify_s11.log")
except:
    pass

print(f"Starting S11 verification at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=7200)
    print(f"GAP process finished at {time.strftime('%H:%M:%S')}")
    if stderr and "error" in stderr.lower():
        print(f"STDERR (errors): {stderr[:1000]}")
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT after 2 hours")

try:
    with open(r"C:\Users\jeffr\Downloads\Lifting\gap_verify_s11.log", "r") as f:
        log = f.read()
    print("\n=== GAP LOG OUTPUT ===")
    print(log)
except FileNotFoundError:
    print("Log file not found")
