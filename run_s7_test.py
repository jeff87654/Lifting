import subprocess
import os

# Test just S7 to verify the C2 optimization fix

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s7.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S7 test to verify C2 optimization fix...")
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

    stdout, stderr = process.communicate(timeout=300)  # 5 min timeout

    if stdout:
        print("Output:")
        print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)

    # Read output file
    output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s7_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file:")
        print("=" * 50)
        with open(output_file, 'r') as f:
            print(f.read())

except subprocess.TimeoutExpired:
    print("Process timed out after 5 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
