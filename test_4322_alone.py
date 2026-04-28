import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n=== Testing partition [4,3,2,2] alone ===\\n\\n");

# First compute S10 to populate cache
result10 := CountAllConjugacyClassesFast(10);
Print("S10 = ", result10, " (should be 1593)\\n\\n");

# Now test [4,3,2,2] partition of S11 in isolation
Print("Testing [4,3,2,2] partition of S11:\\n");
n := 11;
partition := [4, 3, 2, 2];
G := SymmetricGroup(n);
startTime := Runtime();
result := FindFPFClassesForPartition(n, partition);
elapsed := (Runtime() - startTime) / 1000.0;
Print("Partition [4,3,2,2] count: ", Length(result), "\\n");
Print("Expected: 195\\n");
if Length(result) = 195 then
    Print("PASS\\n");
else
    Print("FAIL (off by ", 195 - Length(result), ")\\n");
fi;
Print("Time: ", elapsed, "s\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_4322_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_4322_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

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
# Only print the last part of stdout
lines = stdout.split('\n')
for line in lines:
    if 'Testing' in line or 'count' in line or 'Expected' in line or 'PASS' in line or 'FAIL' in line or '4322' in line or 'S10' in line or 'partition' in line.lower():
        print(line)
print("\n--- Full tail ---")
print('\n'.join(lines[-30:]))
