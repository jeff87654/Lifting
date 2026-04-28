"""Test centralizer optimization on specific S12 partitions with A_n chief factors."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_centralizer_opt3.log"

# Test partitions that have non-abelian simple chief factors
# [8,4] has A_8 factor (TG(8,49)=A_8), index > 2 in product with TG(4,*)
# [6,6] has A_6 factor, same issue
# Reference counts from s12_partition_classes_output.txt
gap_commands = (
    f'LogTo("{log_file}");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    '\n'
    'Print("Testing [8,4] of S12...\\n");\n'
    'startTime := Runtime();\n'
    'r := FindFPFClassesForPartition(12, [8,4]);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("  [8,4] = ", Length(r), " classes (expected 1260), time = ", elapsed, "s\\n");\n'
    'if Length(r) = 1260 then Print("  PASS\\n"); else Print("  FAIL!\\n"); fi;\n'
    '\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    '\n'
    'Print("Testing [6,6] of S12...\\n");\n'
    'startTime := Runtime();\n'
    'r := FindFPFClassesForPartition(12, [6,6]);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("  [6,6] = ", Length(r), " classes (expected 473), time = ", elapsed, "s\\n");\n'
    'if Length(r) = 473 then Print("  PASS\\n"); else Print("  FAIL!\\n"); fi;\n'
    '\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    '\n'
    'Print("Testing [6,4,2] of S12...\\n");\n'
    'startTime := Runtime();\n'
    'r := FindFPFClassesForPartition(12, [6,4,2]);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("  [6,4,2] = ", Length(r), " classes (expected 2547), time = ", elapsed, "s\\n");\n'
    'if Length(r) = 2547 then Print("  PASS\\n"); else Print("  FAIL!\\n"); fi;\n'
    '\n'
    'LogTo();\nQUIT;\n'
)

with open(r"C:\Users\jeffr\Downloads\Lifting\test_centralizer_opt3.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_centralizer_opt3.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting partition tests at {time.strftime('%H:%M:%S')}...")
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
# Print key lines
for line in log.strip().split('\n'):
    if any(kw in line for kw in ['Testing', 'PASS', 'FAIL', 'classes', 'time =', 'LiftThroughLayer [size=20160', 'LiftThroughLayer [size=360']):
        print(line)
