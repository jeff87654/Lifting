import subprocess
import os

# Test S8 WITHOUT loading cohomology module to get baseline

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s8_nocohom_output.txt");
Print("Testing S8 WITHOUT cohomology module (baseline)\\n");
Print("=================================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# FORCE disable H^1 complements so cohomology module is NEVER loaded
USE_H1_COMPLEMENTS := false;

Print("\\nUSE_H1_COMPLEMENTS = ", USE_H1_COMPLEMENTS, "\\n");
Print("\\nTesting S8 (expected: 296):\\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\n\\nFinal S8 Result: ", result, "\\n");
Print("Expected: 296\\n");
if result = 296 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL (off by ", 296 - result, ")\\n");
fi;
Print("Time: ", elapsed, " seconds\\n");

LogTo();
QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s8_nocohom.g", "w") as f:
    f.write(gap_commands)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s8_nocohom.g"

print("Testing S8 WITHOUT cohomology module...")
print()

try:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=600)  # 10 min timeout

    if stdout:
        print("Output:")
        print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)

    # Read output file
    output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s8_nocohom_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file:")
        print("=" * 50)
        with open(output_file, 'r') as f:
            print(f.read())

except subprocess.TimeoutExpired:
    print("Process timed out after 10 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
