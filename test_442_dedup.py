"""Test [4,4,2] with deduplication tracing."""

import subprocess
import os
import time

gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt", "Tracing [4,4,2]...\\n");

partition := [4, 4, 2];;
n := 10;;

# Step 1: Build normalizer
N := BuildConjugacyTestGroup(n, partition);;
AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
    "|N| = ", Size(N), "\\n");

# Step 2: Enumerate all combos manually
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));;

all_fpf := [];;
combo := 0;;

for T1 in transitiveLists[1] do
    for T2 in transitiveLists[2] do
        for T3 in transitiveLists[3] do
            combo := combo + 1;;
            shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];;
            offs := [0, 4, 8];;

            cacheKey := ComputeCacheKey([T1, T2, T3]);;
            if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
                Append(all_fpf, FPF_SUBDIRECT_CACHE.(cacheKey));;
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
                    "Combo ", combo, ": cache hit (", Length(FPF_SUBDIRECT_CACHE.(cacheKey)), ")\\n");
            else
                P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;
                liftResult := FindFPFClassesByLifting(P, shifted, offs);;
                FPF_SUBDIRECT_CACHE.(cacheKey) := liftResult;;
                Append(all_fpf, liftResult);;
                AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
                    "Combo ", combo, ": computed ", Length(liftResult), " (total: ", Length(all_fpf), ")\\n");
            fi;;
        od;;
    od;;
od;;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
    "\\nTotal raw FPF: ", Length(all_fpf), "\\n");
AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
    "Starting dedup under |N|=", Size(N), "...\\n");

# Step 3: Deduplication
unique := [];;
byInvariant := rec();;
invFunc := ComputeSubgroupInvariant;;
count := 0;;

for H in all_fpf do
    count := count + 1;;
    if count mod 50 = 0 then
        AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
            "  Processed ", count, "/", Length(all_fpf), ", unique: ", Length(unique), "\\n");
    fi;;
    AddIfNotConjugate(N, H, unique, byInvariant, invFunc);;
od;;

AppendTo("C:/Users/jeffr/Downloads/Lifting/442_dedup.txt",
    "\\nFinal unique: ", Length(unique), "\\nDONE\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_dedup.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_dedup.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\442_dedup.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing [4,4,2] with dedup tracing...")
start = time.time()

with open(r"C:\Users\jeffr\Downloads\Lifting\442_dedup_stdout.txt", "w") as stdout_f:
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
    print("\nTrace:")
    with open(trace_file, 'r') as f:
        print(f.read())
