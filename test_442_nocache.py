"""Test [4,4,2] without using FPF cache."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_nocache.txt", "Testing without cache...\\n");

partition := [4, 4, 2];;
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));;

combo := 0;;
for i1 in [1..5] do
    for i2 in [1..5] do
        combo := combo + 1;;

        T1 := transitiveLists[1][i1];;
        T2 := transitiveLists[2][i2];;
        T3 := transitiveLists[3][1];;

        shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];;
        offs := [0, 4, 8];;
        P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;

        AppendTo("C:/Users/jeffr/Downloads/Lifting/442_nocache.txt",
            "Combo ", combo, ": T(4,", i1, ")xT(4,", i2, ") |P|=", Size(P), " ... ");

        liftResult := FindFPFClassesByLifting(P, shifted, offs);;

        AppendTo("C:/Users/jeffr/Downloads/Lifting/442_nocache.txt",
            Length(liftResult), " FPF\\n");

        # DON'T store in cache, just discard
        Unbind(liftResult);;
        GASMAN("collect");;
    od;;
od;;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_nocache.txt", "\\nAll 25 combos done!\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_nocache.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_nocache.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\442_nocache.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing [4,4,2] without cache...")
start = time.time()

with open(os.devnull, "w") as devnull:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=devnull,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )
    process.wait(timeout=600)

elapsed = time.time() - start
print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(trace_file):
    print("\nTrace:")
    with open(trace_file, 'r') as f:
        print(f.read())
