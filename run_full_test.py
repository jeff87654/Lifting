import subprocess
import os

# Run the full test suite to verify S2-S10

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/full_test_output.txt");
Print("Full Test Run S2-S10\\n");
Print("====================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

totalTime := 0;
allPass := true;

for n in [2..10] do
    expected := known[n];
    Print("\\n========================================\\n");
    Print("Testing S_", n, " (expected: ", expected, ")\\n");
    Print("========================================\\n");

    # Clear cache to ensure fresh computation
    LIFT_CACHE := rec();

    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    totalTime := totalTime + elapsed;

    Print("\\nS_", n, " Result: ", result, "\\n");
    Print("Expected: ", expected, "\\n");
    if result = expected then
        Print("Status: PASS\\n");
    else
        Print("Status: FAIL (off by ", expected - result, ")\\n");
        allPass := false;
    fi;
    Print("Time: ", elapsed, " seconds\\n");
od;

Print("\\n\\n========================================\\n");
Print("FINAL SUMMARY\\n");
Print("========================================\\n");
Print("Total time: ", totalTime, " seconds\\n");
if allPass then
    Print("All tests PASSED!\\n");
else
    Print("Some tests FAILED\\n");
fi;

LogTo();
QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_full_test.g", "w") as f:
    f.write(gap_commands)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_full_test.g"

print("Running full test suite S2-S10...")
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

    stdout, stderr = process.communicate(timeout=3600)  # 60 min timeout

    if stdout:
        print("Output:")
        print(stdout[-5000:])  # Last 5000 chars
    if stderr:
        print("Errors (last 2000 chars):")
        print(stderr[-2000:])

    # Read output file
    output_file = r"C:\Users\jeffr\Downloads\Lifting\full_test_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file (last 3000 chars):")
        print("=" * 50)
        with open(output_file, 'r') as f:
            content = f.read()
            print(content[-3000:])

except subprocess.TimeoutExpired:
    print("Process timed out after 60 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
