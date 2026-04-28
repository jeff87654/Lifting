import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_verify_fix.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Testing S2-S10 (fresh, no caches) ===\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(10);
t1 := Runtime();
Print("S2-S10 total time: ", StringTime(t1 - t0), "\\n");
Print("S10 result: ", result, "\\n");
if result = 1593 then
    Print("S10 PASS\\n");
else
    Print("S10 FAIL (expected 1593)\\n");
fi;

# Check S8 and S9 from cache
s8 := LIFT_CACHE.("8");
s9 := LIFT_CACHE.("9");
Print("S8 = ", s8, " (expected 296): ", s8 = 296, "\\n");
Print("S9 = ", s9, " (expected 554): ", s9 = 554, "\\n");

Print("\\n=== Testing S11 (cached S1-S10) ===\\n");
t0 := Runtime();
result11 := CountAllConjugacyClassesFast(11);
t1 := Runtime();
Print("S11 time: ", StringTime(t1 - t0), "\\n");
Print("S11 result: ", result11, "\\n");
if result11 = 3094 then
    Print("S11 PASS\\n");
else
    Print("S11 FAIL (expected 3094)\\n");
fi;

Print("\\nAll tests complete.\\n");
LogTo();
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

print(f"Starting GAP verification at {time.strftime('%H:%M:%S')}")
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

print(f"GAP finished at {time.strftime('%H:%M:%S')}")
with open(r"C:\Users\jeffr\Downloads\Lifting\gap_verify_fix.log", "r") as f:
    log = f.read()
print(log[-3000:] if len(log) > 3000 else log)
