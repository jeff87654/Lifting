"""Quick test: verify S2-S10 still correct with centralizer optimization."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_centralizer_opt.log"

gap_commands = (
    f'LogTo("{log_file}");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    'LIFT_CACHE := rec();\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'Print("Testing S2-S10 with centralizer optimization...\\n");\n'
    'startTime := Runtime();\n'
    'result := CountAllConjugacyClassesFast(10);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("S10 = ", result, " (expected 1593), time = ", elapsed, "s\\n");\n'
    'if result = 1593 then Print("PASS\\n"); else Print("FAIL!\\n"); fi;\n'
    'LogTo();\nQUIT;\n'
)

with open(r"C:\Users\jeffr\Downloads\Lifting\test_centralizer_opt.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_centralizer_opt.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 test at {time.strftime('%H:%M:%S')}...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
print(log[-500:])
