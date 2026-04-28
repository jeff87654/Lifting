import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the FPF cache to force fresh computation
FPF_SUBDIRECT_CACHE := rec();

Print("\\n========================================\\n");
Print("S10 Verification Test (Fresh Computation)\\n");
Print("========================================\\n\\n");

ResetH1OrbitalStats();

result := CountAllConjugacyClassesFast(10);
Print("\\n========================================\\n");
Print("S10 conjugacy class count: ", result, "\\n");
Print("Expected: 1593\\n");
if result = 1593 then
    Print("SUCCESS: S10 count is correct!\\n");
else
    Print("MISMATCH: Expected 1593, got ", result, "\\n");
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

log_file = r"C:\Users\jeffr\Downloads\Lifting\test_s10_verify_output.txt"

print(f"Running S10 verification test...")
print(f"Output will be written to: {log_file}")

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
    stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout

    # Write to log file
    with open(log_file, "w") as f:
        f.write(stdout)
        if stderr and "Syntax warning" not in stderr:
            f.write("\n\nSTDERR:\n")
            f.write(stderr)

    print(f"Test complete. Output written to {log_file}")

    # Print just the final result summary
    lines = stdout.split('\n')
    for i, line in enumerate(lines):
        if 'S10 conjugacy class count' in line or 'SUCCESS' in line or 'MISMATCH' in line:
            print(line)
        if 'Orbital Statistics' in line:
            # Print the stats section
            for j in range(i, min(i+12, len(lines))):
                print(lines[j])
            break

except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 1 hour")
    sys.exit(1)
