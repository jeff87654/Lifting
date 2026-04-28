"""Test S10 with partition-level tracing."""

import subprocess
import os
import time

gap_commands = '''
OnBreak := function()
    AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_trace.txt", "BREAK LOOP!\\n");
    FORCE_QUIT_GAP(1);
end;
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Override FindFPFClassesForPartition to trace
OriginalFindFPF := FindFPFClassesForPartition;
FindFPFClassesForPartition := function(n, partition)
    local result;
    AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_trace.txt",
        "Starting partition ", partition, "\\n");
    result := OriginalFindFPF(n, partition);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_trace.txt",
        "Finished partition ", partition, ": ", Length(result), " classes\\n");
    return result;
end;

PrintTo("C:/Users/jeffr/Downloads/Lifting/s10_trace.txt", "=== S10 Trace ===\\n");

Print("\\n=== Running S10 ===\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := Runtime() - startTime;

AppendTo("C:/Users/jeffr/Downloads/Lifting/s10_trace.txt",
    "\\n=== FINAL RESULT ===\\n",
    "S10: ", result, " classes\\n",
    "Time: ", elapsed / 1000.0, "s\\n");

Print("Done! Result: ", result, "\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_trace.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_trace.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

trace_file = r"C:\Users\jeffr\Downloads\Lifting\s10_trace.txt"
if os.path.exists(trace_file):
    os.remove(trace_file)

print("Testing S10 with partition tracing...")
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

try:
    stdout, stderr = process.communicate(timeout=2400)
    elapsed = time.time() - start

    print(f"Python timing: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Exit code: {process.returncode}")

    if os.path.exists(trace_file):
        print("\n" + "=" * 60)
        print("TRACE FILE:")
        print("=" * 60)
        with open(trace_file, 'r') as f:
            print(f.read())
    else:
        print("\nTrace file not created!")

except subprocess.TimeoutExpired:
    process.kill()
    print(f"\nTIMEOUT")
    if os.path.exists(trace_file):
        with open(trace_file, 'r') as f:
            print("Partial trace:", f.read())
