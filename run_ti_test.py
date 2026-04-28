import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_ti_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result := CountAllConjugacyClassesFast(10);
t1 := Runtime();
Print("\\n=== RESULT ===\\n");
Print("S10 = ", result, "\\n");
Print("Time = ", StringTime(t1-t0), "\\n");
if result = 1593 then
    Print("PASS\\n");
else
    Print("FAIL (expected 1593)\\n");
fi;
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_ti_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_ti_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S2-S10 regression test at {time.strftime('%H:%M:%S')}")
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

with open(r"C:\Users\jeffr\Downloads\Lifting\gap_ti_test.log", "r") as f:
    log = f.read()

# Print just the result section
if "=== RESULT ===" in log:
    print(log[log.index("=== RESULT ==="):])
else:
    print("No result found in log. Last 500 chars:")
    print(log[-500:])
