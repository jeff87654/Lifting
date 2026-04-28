import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the FPF cache to force fresh computation
FPF_SUBDIRECT_CACHE := rec();

Print("\\n========================================\\n");
Print("S8 Verification Test (Fresh Computation)\\n");
Print("========================================\\n\\n");

ResetH1OrbitalStats();

result := CountAllConjugacyClassesFast(8);
Print("\\n========================================\\n");
Print("S8 conjugacy class count: ", result, "\\n");
Print("Expected: 296\\n");
if result = 296 then
    Print("SUCCESS: S8 count is correct!\\n");
else
    Print("MISMATCH: Expected 296, got ", result, "\\n");
fi;
Print("========================================\\n\\n");

PrintH1OrbitalStats();

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

print("Running S8 verification with fresh computation...")
print()

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
    stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout
    print(stdout)
    if stderr and "Syntax warning" not in stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out")
    sys.exit(1)
