"""Detailed test of [4,4,2] partition with step-by-step tracing."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    AppendTo("C:/Users/jeffr/Downloads/Lifting/442_trace.txt", "\\n*** BREAK LOOP ***\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

LogTrace := function(msg)
    AppendTo("C:/Users/jeffr/Downloads/Lifting/442_trace.txt", msg, "\\n");
end;

PrintTo("C:/Users/jeffr/Downloads/Lifting/442_trace.txt", "=== [4,4,2] Detailed Trace ===\\n");

Print("\\n=== Testing [4,4,2] ===\\n");

# Manual implementation of partition processing to trace each step
partition := [4, 4, 2];
n := 10;

LogTrace("Step 1: Building transitive group lists...");
transitiveLists := List(partition, d ->
    List([1..NrTransitiveGroups(d)], j -> TransitiveGroup(d, j)));
LogTrace(Concatenation("  Sizes: ", String(List(transitiveLists, Length))));

LogTrace("Step 2: Building normalizer...");
N := BuildConjugacyTestGroup(n, partition);
LogTrace(Concatenation("  |N| = ", String(Size(N))));

LogTrace("Step 3: Processing factor combinations...");

all_fpf := [];
combo_count := 0;

for T1 in transitiveLists[1] do
    for T2 in transitiveLists[2] do
        for T3 in transitiveLists[3] do
            combo_count := combo_count + 1;
            LogTrace(Concatenation("  Combo ", String(combo_count), ": T(",
                String(NrMovedPoints(T1)), ",", String(TransitiveIdentification(T1)), ") x T(",
                String(NrMovedPoints(T2)), ",", String(TransitiveIdentification(T2)), ") x T(",
                String(NrMovedPoints(T3)), ",", String(TransitiveIdentification(T3)), ")"));

            # Build shifted factors
            shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];
            offs := [0, 4, 8];

            # Check cache
            cacheKey := ComputeCacheKey([T1, T2, T3]);
            if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
                LogTrace("    Cache HIT");
                Append(all_fpf, FPF_SUBDIRECT_CACHE.(cacheKey));
            else
                LogTrace("    Cache MISS - computing...");
                P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
                LogTrace(Concatenation("    |P| = ", String(Size(P))));

                liftResult := FindFPFClassesByLifting(P, shifted, offs);
                LogTrace(Concatenation("    Found ", String(Length(liftResult)), " FPF subdirects"));

                FPF_SUBDIRECT_CACHE.(cacheKey) := liftResult;
                Append(all_fpf, liftResult);
            fi;
        od;
    od;
od;

LogTrace(Concatenation("\\nStep 4: Total raw FPF: ", String(Length(all_fpf))));
LogTrace("Step 5: Deduplication under normalizer...");

# Simple dedup
unique := [];
for H in all_fpf do
    if not ForAny(unique, U -> RepresentativeAction(N, H, U) <> fail) then
        Add(unique, H);
    fi;
od;

LogTrace(Concatenation("Final unique: ", String(Length(unique))));
LogTrace("\\n=== DONE ===");

Print("Result: ", Length(unique), " unique FPF subdirects\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_442_detailed.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_442_detailed.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\442_trace.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing [4,4,2] with detailed tracing...")
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

stdout, stderr = process.communicate(timeout=600)
elapsed = time.time() - start

print(f"Exit code: {process.returncode}")
print(f"Time: {elapsed:.1f}s")

if os.path.exists(trace_file):
    print("\n" + "=" * 60)
    print("TRACE:")
    print("=" * 60)
    with open(trace_file, 'r') as f:
        content = f.read()
        # Show last 80 lines if long
        lines = content.strip().split('\\n')
        if len(lines) > 80:
            print(f"({len(lines)} lines, showing last 80)")
            print('\\n'.join(lines[-80:]))
        else:
            print(content)
