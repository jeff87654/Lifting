"""Check if GAP is segfaulting."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/segfault_trace.txt", "Starting...\\n");

T43 := TransitiveGroup(4, 3);;
T41 := TransitiveGroup(4, 1);;
T21 := TransitiveGroup(2, 1);;

# First do a few combos to accumulate state
for trial in [1..10] do
    T1 := transitiveLists := List([4], d ->
        List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)))[1];;
od;;

# This is the pattern: after several lifting computations, GAP crashes
# Let me just run several small liftings and see when it crashes

for trial in [1..20] do
    shifted := [T43, ShiftGroup(TransitiveGroup(4, 1 + (trial mod 5)), 4), ShiftGroup(T21, 8)];;
    offs := [0, 4, 8];;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;

    AppendTo("C:/Users/jeffr/Downloads/Lifting/segfault_trace.txt",
        "Trial ", trial, ": |P|=", Size(P), " ... ");

    r := FindFPFClassesByLifting(P, shifted, offs);;

    AppendTo("C:/Users/jeffr/Downloads/Lifting/segfault_trace.txt",
        Length(r), " results\\n");
    GASMAN("collect");;
od;;

AppendTo("C:/Users/jeffr/Downloads/Lifting/segfault_trace.txt", "\\nAll trials done!\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_segfault.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_segfault.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\segfault_trace.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing for segfault pattern...")
start = time.time()

# Use bash -c with $? check to capture actual exit code
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"; echo "EXIT_CODE=$?"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=300)
elapsed = time.time() - start

print(f"Time: {elapsed:.1f}s")
print(f"Bash exit: {process.returncode}")

# Find EXIT_CODE in stdout
for line in stdout.split('\n'):
    if 'EXIT_CODE' in line:
        print(f"GAP exit: {line}")

if os.path.exists(trace_file):
    print("\nTrace:")
    with open(trace_file, 'r') as f:
        print(f.read())
