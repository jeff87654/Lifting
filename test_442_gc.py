"""Test [4,4,2] with forced GC before combo 13."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt", "Tracing [4,4,2] with GC...\\n");

partition := [4, 4, 2];;
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));;

combo := 0;;
for T1 in transitiveLists[1] do
    for T2 in transitiveLists[2] do
        for T3 in transitiveLists[3] do
            combo := combo + 1;;

            if combo = 13 then
                # Force full garbage collection
                GASMAN("collect");;
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt",
                    "GC done before combo 13. Memory: ", GasmanStatistics().partial.livekb, "kb live\\n");
            fi;;

            shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];;
            offs := [0, 4, 8];;
            cacheKey := ComputeCacheKey([T1, T2, T3]);;

            if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt",
                    "Combo ", combo, ": cache hit\\n");
            else
                P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt",
                    "Combo ", combo, ": computing |P|=", Size(P), "...\\n");
                liftResult := FindFPFClassesByLifting(P, shifted, offs);;
                FPF_SUBDIRECT_CACHE.(cacheKey) := liftResult;;
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt",
                    "  Found ", Length(liftResult), "\\n");
            fi;;
        od;;
    od;;
od;;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_gc.txt", "\\nAll 25 combos done!\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_gc.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_gc.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\442_gc.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing [4,4,2] with forced GC...")
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
