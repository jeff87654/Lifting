"""Test centralizer optimization on partitions with A_n chief factors.
Tests the specific combos that were slow (A_6/A_8 chief factors)."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_centralizer_opt2.log"

gap_commands = (
    f'LogTo("{log_file}");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    '\n'
    '# Test S11 (has [8,3], [7,4] etc partitions with non-abelian factors)\n'
    'Print("Computing S11...\\n");\n'
    'startTime := Runtime();\n'
    'result := CountAllConjugacyClassesFast(11);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("S11 = ", result, " (expected 3094), time = ", elapsed, "s\\n");\n'
    'if result = 3094 then Print("S11 PASS\\n"); else Print("S11 FAIL!\\n"); fi;\n'
    '\n'
    '# Test S12 (has [8,4], [6,6] etc)\n'
    'Print("Computing S12...\\n");\n'
    'startTime := Runtime();\n'
    'result := CountAllConjugacyClassesFast(12);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("S12 = ", result, " (expected 10723), time = ", elapsed, "s\\n");\n'
    'if result = 10723 then Print("S12 PASS\\n"); else Print("S12 FAIL!\\n"); fi;\n'
    '\n'
    'LogTo();\nQUIT;\n'
)

with open(r"C:\Users\jeffr\Downloads\Lifting\test_centralizer_opt2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_centralizer_opt2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S11-S12 test at {time.strftime('%H:%M:%S')}...")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)
print(f"Finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
# Print last lines
lines = log.strip().split('\n')
for line in lines[-30:]:
    print(line)
