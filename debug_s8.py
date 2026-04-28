import subprocess
import os

# Debug S8 to find where the 6 missing subgroups are

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Test without H1 optimization to get baseline
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_s8_output.txt");
Print("Debugging S8 - Testing with H1 disabled\\n");
Print("==========================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# Disable H1 optimization
USE_H1_COMPLEMENTS := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear cache to get fresh computation
LIFT_CACHE := rec();

Print("\\nTesting S8 with H1 DISABLED:\\n");
Print("===========================\\n");
startTime := Runtime();
result8_no_h1 := CountAllConjugacyClassesFast(8);
elapsed8 := (Runtime() - startTime) / 1000.0;
Print("\\nS8 Result (no H1): ", result8_no_h1, "\\n");
Print("Expected: 296\\n");
if result8_no_h1 = 296 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL (off by ", 296 - result8_no_h1, ")\\n");
fi;
Print("Time: ", elapsed8, " seconds\\n");

LogTo();
QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_s8.g", "w") as f:
    f.write(gap_commands)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_s8.g"

print("Debugging S8 - Testing with H1 disabled...")
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

    stdout, stderr = process.communicate(timeout=1800)  # 30 min timeout

    if stdout:
        print("Output:")
        print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)

    # Read output file
    output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_s8_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file:")
        print("=" * 50)
        with open(output_file, 'r') as f:
            print(f.read())

except subprocess.TimeoutExpired:
    print("Process timed out after 30 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
