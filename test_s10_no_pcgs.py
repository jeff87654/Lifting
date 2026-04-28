"""
Time S10 computation with C2 optimization, Pcgs cocycle method disabled.
"""

import subprocess
import os
import time

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Disable buggy Pcgs cocycle method by redefining ComputeCocycleSpace
# to only use the original FP-group method
MakeReadWriteGlobal("ComputeCocycleSpace");
ComputeCocycleSpace := function(module)
    return ComputeCocycleSpaceOriginal(module);
end;
MakeReadOnlyGlobal("ComputeCocycleSpace");

Print("\\n");
Print("===========================================\\n");
Print("Timing S10 with C2 optimization enabled\\n");
Print("(Pcgs cocycle method disabled)\\n");
Print("===========================================\\n\\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
totalTime := (Runtime() - startTime) / 1000.0;

Print("\\n===========================================\\n");
Print("S10 Result: ", result, "\\n");
Print("Expected: 1593\\n");
if result = 1593 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL\\n");
fi;
Print("Total time: ", totalTime, " seconds\\n");
Print("===========================================\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s10_no_pcgs.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s10_no_pcgs.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S10 timing test (Pcgs cocycle method disabled)...")
print("=" * 60)

start = time.time()

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)

elapsed = time.time() - start

print(stdout)
print(f"\nWall clock time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

if "FAIL" in stdout:
    print("\nTest FAILED - wrong count")
if "Error" in stderr:
    print("\nErrors encountered:")
    for line in stderr.split('\n'):
        if 'Error' in line:
            print(line)
