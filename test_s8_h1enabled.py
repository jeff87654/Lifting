import subprocess
import os

# Test S8 WITH H1 complements enabled (but cohomolo disabled)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s8_h1enabled_output.txt");
Print("Testing S8 WITH H^1 complements enabled (cohomolo disabled)\\n");
Print("=============================================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# USE_H1_COMPLEMENTS is already true by default
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
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s8_h1enabled.g", "w") as f:
    f.write(gap_commands)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s8_h1enabled.g"

print("Testing S8 WITH H^1 complements enabled...")
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
    output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s8_h1enabled_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file:")
        print("=" * 50)
        with open(output_file, 'r') as f:
            content = f.read()
            # Print last 100 lines to see results
            lines = content.split('\n')
            if len(lines) > 100:
                print("... (truncated, showing last 100 lines) ...\n")
                print('\n'.join(lines[-100:]))
            else:
                print(content)

except subprocess.TimeoutExpired:
    print("Process timed out after 10 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
