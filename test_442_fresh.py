"""Fresh test of [4,4,2] partition."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    AppendTo("C:/Users/jeffr/Downloads/Lifting/442_fresh.txt", "\\n*** BREAK ***\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_fresh.txt", "Starting...\\n");

Print("\\n=== [4,4,2] Fresh Test ===\\n");

startTime := Runtime();
result := FindFPFClassesForPartition(10, [4, 4, 2]);
elapsed := Runtime() - startTime;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_fresh.txt",
    "Done!\\n",
    "Classes: ", Length(result), "\\n",
    "Time: ", elapsed / 1000.0, "s\\n");

Print("Result: ", Length(result), " classes\\n");
Print("Time: ", elapsed / 1000.0, "s\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_fresh.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_fresh.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

result_file = r"C:\Users\jeffr\Downloads\Lifting\442_fresh.txt"
if os.path.exists(result_file):
    os.remove(result_file)

print("Testing [4,4,2] partition (fresh)...")
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

stdout, stderr = process.communicate(timeout=300)
elapsed = time.time() - start

print(f"Exit code: {process.returncode}")
print(f"Time: {elapsed:.1f}s")

if os.path.exists(result_file):
    print("\nRESULT FILE:")
    with open(result_file, 'r') as f:
        print(f.read())
else:
    print("\nNo result file!")

# Show last lines of stdout
lines = [l for l in stdout.strip().split('\\n') if l.strip()]
print(f"\nSTDOUT ({len(lines)} lines, last 10):")
for line in lines[-10:]:
    print(line)
