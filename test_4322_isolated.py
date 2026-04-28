import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Testing [4,3,2,2] partition of S11 in isolation ===\\n\\n");

n := 11;
partition := [4, 3, 2, 2];

Print("Calling FindFPFClassesForPartition(11, [4,3,2,2])...\\n");
startTime := Runtime();
result := FindFPFClassesForPartition(n, partition);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\nPartition [4,3,2,2] count: ", Length(result), "\\n");
Print("Expected: 195\\n");
if Length(result) = 195 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL (off by ", 195 - Length(result), ")\\n");
fi;
Print("Time: ", elapsed, "s\\n");

Print("\\n=== H^1 Timing Stats ===\\n");
PrintH1TimingStats();

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_4322_isolated_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_4322_isolated_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

start = time.time()
print("Testing [4,3,2,2] partition alone...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)
wall = time.time() - start

print(f"Wall clock: {wall:.1f}s\n")
# Print relevant output
for line in stdout.split('\n'):
    if any(kw in line for kw in ['count', 'Expected', 'PASS', 'FAIL', 'Status', 'Time:', '===', 'H^1', 'Fallback', 'fallback', 'method calls']):
        print(line)
