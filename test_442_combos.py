"""Test [4,4,2] combos one at a time to find which causes the crash."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

partition := [4, 4, 2];
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt", "Testing combos...\\n");

combo := 0;
for i1 in [1..Length(transitiveLists[1])] do
    for i2 in [1..Length(transitiveLists[2])] do
        for i3 in [1..Length(transitiveLists[3])] do
            combo := combo + 1;
            T1 := transitiveLists[1][i1];
            T2 := transitiveLists[2][i2];
            T3 := transitiveLists[3][i3];

            AppendTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt",
                "Combo ", combo, ": T(4,", i1, ") x T(4,", i2, ") x T(2,", i3, ")\\n");

            cacheKey := ComputeCacheKey([T1, T2, T3]);
            if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt",
                    "  CACHE HIT: ", Length(FPF_SUBDIRECT_CACHE.(cacheKey)), " results\\n");
            else
                shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];
                offs := [0, 4, 8];
                P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt",
                    "  Computing |P|=", Size(P), "...\\n");

                startTime := Runtime();
                liftResult := FindFPFClassesByLifting(P, shifted, offs);
                elapsed := Runtime() - startTime;

                FPF_SUBDIRECT_CACHE.(cacheKey) := liftResult;

                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt",
                    "  Found ", Length(liftResult), " FPF in ", elapsed/1000.0, "s\\n");
            fi;
        od;
    od;
od;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_combos.txt", "\\nAll combos done!\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_combos.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_combos.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\442_combos.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing [4,4,2] combos individually...")
start = time.time()

with open(r"C:\Users\jeffr\Downloads\Lifting\442_combos_stdout.txt", "w") as stdout_f:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=stdout_f,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )
    process.wait(timeout=600)

elapsed = time.time() - start
print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

if os.path.exists(trace_file):
    print("\nCombo trace:")
    with open(trace_file, 'r') as f:
        print(f.read())
