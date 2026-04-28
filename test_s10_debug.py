"""Test S10 with detailed debugging."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_result.txt", "ERROR: Break loop\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Log progress to file
LogProgress := function(msg)
    AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_progress.txt", msg, "\\n");
end;

PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_progress.txt", "Starting S10...\\n");

Print("\\n=== Running S10 Test ===\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := Runtime() - startTime;

AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_progress.txt", "Completed! Result: ", result, "\\n");

# Write result to file
PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_result.txt",
    "S10 conjugacy classes: ", result, "\\n",
    "Expected: 1593\\n",
    "Time: ", elapsed / 1000.0, "s\\n");

Print("\\nDone! Result: ", result, "\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_debug.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_debug.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Delete old files
for f in ["s10_result.txt", "s10_progress.txt"]:
    path = os.path.join(r"C:\Users\jeffr\Downloads\Lifting", f)
    if os.path.exists(path):
        os.remove(path)

print("Testing S10 with debugging...")
print("=" * 60)

start = time.time()

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
    stdout, stderr = process.communicate(timeout=2400)
    elapsed = time.time() - start

    print(f"\nPython timing: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Exit code: {process.returncode}")

    # Show progress file
    progress_file = r"C:\Users\jeffr\Downloads\Lifting\s10_progress.txt"
    if os.path.exists(progress_file):
        print("\n" + "=" * 60)
        print("PROGRESS FILE:")
        print("=" * 60)
        with open(progress_file, 'r') as f:
            print(f.read())

    # Show result file
    result_file = r"C:\Users\jeffr\Downloads\Lifting\s10_result.txt"
    if os.path.exists(result_file):
        print("\n" + "=" * 60)
        print("RESULT FILE:")
        print("=" * 60)
        with open(result_file, 'r') as f:
            print(f.read())
    else:
        print("\nResult file not created")

    # Show stderr if any real errors
    if stderr and "Syntax warning" not in stderr:
        print("\nSTDERR (filtered):")
        for line in stderr.split('\n'):
            if 'Syntax warning' not in line and 'Unbound global' not in line and line.strip():
                print(line)

except subprocess.TimeoutExpired:
    process.kill()
    print(f"\nTIMEOUT")
