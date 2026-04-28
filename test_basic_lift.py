"""Most basic test of FindFPFClassesByLifting."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/basic_lift.txt", "Starting basic test...\\n");

T43 := TransitiveGroup(4, 3);;
T21 := TransitiveGroup(2, 1);;

shifted := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];;
offs := [0, 4, 8];;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;

AppendTo("C:/Users/jeffr/Downloads/Lifting/basic_lift.txt", "|P| = ", Size(P), "\\n");

r := FindFPFClassesByLifting(P, shifted, offs);;

AppendTo("C:/Users/jeffr/Downloads/Lifting/basic_lift.txt",
    "Found: ", Length(r), " FPF subdirects\\nDONE\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_basic_lift.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_basic_lift.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

result_file = r"C:\Users\jeffr\Downloads\Lifting\basic_lift.txt"
if os.path.exists(result_file):
    os.remove(result_file)

print("Basic FindFPFClassesByLifting test...")
start = time.time()

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=120)
elapsed = time.time() - start

print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(result_file):
    print("\nResult file:")
    with open(result_file, 'r') as f:
        print(f.read())
else:
    print("No result file!")

# Show last lines of stdout
lines = [l for l in stdout.strip().split('\n') if l.strip()]
print(f"\nStdout last 5 lines:")
for line in lines[-5:]:
    print(f"  {line}")
