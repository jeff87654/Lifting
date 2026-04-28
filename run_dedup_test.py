import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_dedup_test.log"

gap_commands = f'''
LogTo("{log_file}");
Print("Dedup Optimization Test (orbit invariants + C2 skip)\\n");
Print("=====================================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for accurate timing
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("\\nImages package available: ", IMAGES_AVAILABLE, "\\n\\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

allPass := true;
for n in [2..10] do
    Print("\\n========================================\\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\\n");
    Print("========================================\\n");
    # Clear caches between runs for independent timing
    FPF_SUBDIRECT_CACHE := rec();
    LIFT_CACHE := rec();
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\\nS_", n, " Result: ", result, "\\n");
    Print("Expected: ", known[n], "\\n");
    if result = known[n] then
        Print("Status: PASS\\n");
    else
        Print("Status: FAIL\\n");
        allPass := false;
    fi;
    Print("Time: ", elapsed, " seconds\\n");
od;

Print("\\n\\n========================================\\n");
if allPass then
    Print("ALL TESTS PASSED\\n");
else
    Print("SOME TESTS FAILED\\n");
fi;
Print("========================================\\n");
LogTo();
QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S2-S10 verification with dedup optimizations...")
print(f"Output will be logged to: {log_file}")

# Run GAP via Cygwin bash
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
    stdout, stderr = process.communicate(timeout=3600)
    if stderr:
        print("Stderr:", stderr[:500])
except subprocess.TimeoutExpired:
    print("Timed out after 1 hour")
    process.kill()

# Read results from the LogTo file
log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_dedup_test.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    # Print summary lines
    lines = log.split('\n')
    for line in lines:
        if any(kw in line for kw in ['Result', 'Expected', 'Status', 'PASS', 'FAIL', 'Total S_', 'Time:', 'Partition', 'Final count', 'LiftThroughLayer', 'ALL TESTS']):
            print(line.strip())
else:
    print("Log file not found!")
    if stdout:
        print("Stdout:", stdout[-2000:])
