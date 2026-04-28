import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_debug_s6.log"

gap_commands = f'''
LogTo("{log_file}");
Print("Debug S6 Test - No Canonical Dedup\\n");
Print("====================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Disable canonical dedup to test if that's the issue
IMAGES_AVAILABLE := false;
Print("IMAGES_AVAILABLE forced to: ", IMAGES_AVAILABLE, "\\n\\n");

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

result := CountAllConjugacyClassesFast(6);
Print("\\nS6 result (no canonical): ", result, "\\n");
Print("Expected: 56\\n");
if result = 56 then
    Print("PASS - canonical dedup was the problem\\n");
else
    Print("FAIL - issue is elsewhere (orbit invariant?)\\n");
fi;
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

print("Running S6 debug test (canonical dedup disabled)...")

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
    stdout, stderr = process.communicate(timeout=300)
except subprocess.TimeoutExpired:
    print("Timed out")
    process.kill()

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_debug_s6.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    # Show last part
    lines = log.split('\n')
    for line in lines:
        if 'Partition' in line or 'Final count' in line or 'Result' in line or 'PASS' in line or 'FAIL' in line or 'Expected' in line or 'Total' in line:
            print(line)
else:
    print("Log not found")
    if stdout:
        print(stdout[-1000:])
