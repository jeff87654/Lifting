"""Test the specific failing combination: T(4,3) x T(4,3) x T(2,1)."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_trace.txt", "\\n*** BREAK LOOP ***\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

LogTrace := function(msg)
    AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_trace.txt", msg, "\\n");
end;

PrintTo("C:/Users/jeffr/Downloads/Lifting/combo13_trace.txt", "=== T(4,3) x T(4,3) x T(2,1) Test ===\\n");

# Build the specific product
T1 := TransitiveGroup(4, 3);  # D8
T2 := TransitiveGroup(4, 3);  # D8
T3 := TransitiveGroup(2, 1);  # C2

LogTrace(Concatenation("T1 = T(4,3): ", String(StructureDescription(T1)), ", |T1| = ", String(Size(T1))));
LogTrace(Concatenation("T2 = T(4,3): ", String(StructureDescription(T2)), ", |T2| = ", String(Size(T2))));
LogTrace(Concatenation("T3 = T(2,1): ", String(StructureDescription(T3)), ", |T3| = ", String(Size(T3))));

shifted := [T1, ShiftGroup(T2, 4), ShiftGroup(T3, 8)];
offs := [0, 4, 8];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
LogTrace(Concatenation("\\nP = T1 x T2 x T3, |P| = ", String(Size(P))));

# Check chief series
series := ChiefSeries(P);
LogTrace(Concatenation("Chief series length: ", String(Length(series))));
for i in [1..Length(series)] do
    LogTrace(Concatenation("  series[", String(i), "]: |G| = ", String(Size(series[i]))));
od;

# Check if maximal descent will be used
LogTrace(Concatenation("\\nShouldUseMaximalDescent: ", String(ShouldUseMaximalDescent(P, series))));

LogTrace("\\nCalling FindFPFClassesByLifting...");
Print("Calling FindFPFClassesByLifting...\\n");

startTime := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := Runtime() - startTime;

LogTrace(Concatenation("\\nResult: ", String(Length(result)), " FPF subdirects"));
LogTrace(Concatenation("Time: ", String(elapsed / 1000.0), "s"));

Print("Result: ", Length(result), " FPF subdirects\\n");
Print("Time: ", elapsed / 1000.0, "s\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_combo13.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_combo13.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\combo13_trace.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing T(4,3) x T(4,3) x T(2,1)...")
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

stdout, stderr = process.communicate(timeout=120)
elapsed = time.time() - start

print(f"Exit code: {process.returncode}")
print(f"Time: {elapsed:.1f}s")

if os.path.exists(trace_file):
    print("\n" + "=" * 60)
    print("TRACE:")
    print("=" * 60)
    with open(trace_file, 'r') as f:
        print(f.read())

print("\nSTDOUT (last 20 lines):")
for line in stdout.strip().split('\\n')[-20:]:
    print(line)
