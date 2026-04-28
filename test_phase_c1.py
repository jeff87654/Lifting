import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_phase_c1.log"

gap_commands = f'''
LogTo("{log_file}");
Print("=== Phase C1 Re-enabled Test ===\\n");
Print("Testing S2-S10 and S11 with outerNormBase := partNormalizer\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test S2-S10
Print("--- S2-S10 ---\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(10);
t1 := Runtime();
Print("S10 = ", result, " (expected 1593)\\n");
Print("Time: ", (t1 - t0)/1000.0, "s\\n");
if result = 1593 then
    Print("S10 PASS\\n\\n");
else
    Print("S10 FAIL!!! Got ", result, " expected 1593\\n\\n");
fi;

# Test S11
Print("--- S11 ---\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(11);
t1 := Runtime();
Print("S11 = ", result, " (expected 3094)\\n");
Print("Time: ", (t1 - t0)/1000.0, "s\\n");
if result = 3094 then
    Print("S11 PASS\\n\\n");
else
    Print("S11 FAIL!!! Got ", result, " expected 3094\\n\\n");
fi;

Print("=== Test Complete ===\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_phase_c1.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_phase_c1.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}")
print(f"Log file: {log_file}")

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
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

if os.path.exists(r"C:\Users\jeffr\Downloads\Lifting\test_phase_c1.log"):
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_phase_c1.log", "r") as f:
        log = f.read()
    print(log)
else:
    print("No log file found!")
    print("STDOUT:", stdout[:2000])
    print("STDERR:", stderr[:2000])
