"""Test combo 13 after computing combos 7 and 8 (the big ones)."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt", "Testing sequential combos...\\n");

# Compute the big combos first (7 and 8) to see if accumulated results cause issues
T42 := TransitiveGroup(4, 2);
T43 := TransitiveGroup(4, 3);
T21 := TransitiveGroup(2, 1);

# Combo 7: T(4,2) x T(4,2) x T(2,1) - 112 results
shifted7 := [T42, ShiftGroup(TransitiveGroup(4,2), 4), ShiftGroup(T21, 8)];
offs := [0, 4, 8];
P7 := Group(Concatenation(List(shifted7, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt", "Computing combo 7 (T42 x T42 x C2)...\\n");
r7 := FindFPFClassesByLifting(P7, shifted7, offs);
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt",
    "  Result: ", Length(r7), " FPF\\n");

# Combo 8: T(4,2) x T(4,3) x T(2,1) - 112 results
shifted8 := [T42, ShiftGroup(T43, 4), ShiftGroup(T21, 8)];
P8 := Group(Concatenation(List(shifted8, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt", "Computing combo 8 (T42 x T43 x C2)...\\n");
r8 := FindFPFClassesByLifting(P8, shifted8, offs);
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt",
    "  Result: ", Length(r8), " FPF\\n");

# Force garbage collection
GASMAN("collect");

AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt", "Computing combo 13 (T43 x T43 x C2)...\\n");

# Combo 13: T(4,3) x T(4,3) x T(2,1) - the failing one
shifted13 := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
P13 := Group(Concatenation(List(shifted13, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt",
    "  |P| = ", Size(P13), "\\n");

r13 := FindFPFClassesByLifting(P13, shifted13, offs);

AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt",
    "  Result: ", Length(r13), " FPF\\n");
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_test.txt", "\\nAll done!\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_combo13_after.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_combo13_after.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\combo13_test.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing combo 13 after big combos 7 & 8...")
start = time.time()

with open(r"C:\Users\jeffr\Downloads\Lifting\combo13_stdout.txt", "w") as stdout_f:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=stdout_f,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )
    process.wait(timeout=300)

elapsed = time.time() - start
print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(trace_file):
    print("\nTrace:")
    with open(trace_file, 'r') as f:
        print(f.read())
